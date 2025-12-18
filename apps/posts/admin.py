# apps/posts/admin.py

from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.utils import timezone
from django.db import transaction  # Import transaction
from datetime import timedelta
import re

from .models import Post, PostImage
from .tasks import process_and_publish_post
from apps.users.models import User

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    readonly_fields = ('id', 'image_url', 'is_text_image', 'created_at')
    can_delete = False

# --- Custom Widget for "Select or Type" functionality ---
class DatalistTextInput(forms.TextInput):
    def __init__(self, datalist_options=None, *args, **kwargs):
        self.datalist_options = datalist_options or []
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        datalist_id = f"{name}_list"
        attrs['list'] = datalist_id
        attrs['autocomplete'] = 'off'
        
        text_input_html = super().render(name, value, attrs, renderer)
        options_html = "".join([f'<option value="{opt}">' for opt in self.datalist_options])
        datalist_html = f'<datalist id="{datalist_id}">{options_html}</datalist>'
        return format_html(text_input_html + datalist_html)


# --- Custom Admin Form ---
class PostAdminForm(forms.ModelForm):
    # 1. Streamlined User Field
    user_identifier = forms.CharField(
        label="User (Select or Type New)",
        help_text="Type a name. Select from dropdown to use existing. Type NEW name to create new.",
        required=True,
        widget=forms.TextInput()
    )

    # 2. Relative Scheduling Fields (Select Options)
    HOURS_CHOICES = [(i, f"{i} hours") for i in range(11)]
    schedule_delay_hours = forms.TypedChoiceField(
        choices=HOURS_CHOICES,
        coerce=int,
        empty_value=0,
        required=False,
        label="Post in (Hours)",
        help_text="Select delay hours."
    )

    MINUTES_CHOICES = [(i, f"{i} minutes") for i in range(5, 60, 5)]
    schedule_delay_minutes = forms.TypedChoiceField(
        choices=MINUTES_CHOICES,
        coerce=int,
        empty_value=0,
        required=False,
        label="Post in (Minutes)",
        help_text="Select delay minutes."
    )

    class Meta:
        model = Post
        fields = '__all__'
        exclude = ('user',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-fill user_identifier
        if self.instance.pk and self.instance.user:
            self.fields['user_identifier'].initial = str(self.instance.user)
        else:
            # Set DEFAULT STATUS to Scheduled for new posts
            self.fields['status'].initial = Post.PostStatus.SCHEDULED
        
        # Populate datalist
        recent_users = User.objects.all().order_by('-last_seen_at')[:100]
        user_options = [str(u) for u in recent_users]
        self.fields['user_identifier'].widget = DatalistTextInput(datalist_options=user_options)


@admin.action(description="🔄 Retry publishing selected posts")
def retry_failed_posts(modeladmin, request, queryset):
    count = 0
    for post in queryset:
        # Don't retry if already posted!
        if post.status == Post.PostStatus.POSTED:
            continue
            
        post.status = Post.PostStatus.PROCESSING
        post.meta_api_error = None
        post.save()
        # Use on_commit to prevent race conditions
        transaction.on_commit(lambda p=post.id: process_and_publish_post.delay(p))
        count += 1
    
    if count > 0:
        modeladmin.message_user(request, f"Successfully queued {count} post(s) for retry.", messages.SUCCESS)
    else:
        modeladmin.message_user(request, "No eligible posts selected for retry.", messages.WARNING)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    form = PostAdminForm
    inlines = [PostImageInline]
    actions = [retry_failed_posts]
    
    list_display = ('post_number', 'user', 'get_status_display_colored', 'scheduled_time', 'created_at', 'is_promotional')
    list_filter = ('status', 'scheduled_time', 'moderation_reason', 'created_at', 'is_promotional')
    search_fields = ('post_number', 'user__name', 'text_content')
    
    readonly_fields = (
        'post_number', 'submission_ip', 'submission_user_agent', 
        'instagram_media_id', 'created_at', 'posted_at',
        'moderation_reason', 'llm_moderation_response',
        'meta_api_status', 'meta_api_error' 
    )
    
    fieldsets = (
        ('Create Post', {
            'description': "Enter username and message.",
            'fields': ('user_identifier', 'text_content')
        }),
        ('Scheduling Options', {
            'description': "Select time delay. Default status is SCHEDULED.",
            'fields': (
                'status', 
                ('schedule_delay_hours', 'schedule_delay_minutes'),
            )
        }),
        ('Advanced / Exact Time & System', {
            'classes': ('collapse',),
            'fields': ('scheduled_time', 'post_number', 'moderation_reason', 'meta_api_status', 'meta_api_error', 'instagram_media_id', 'created_at', 'posted_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        
        # 1. Handle User
        user_input = form.cleaned_data.get('user_identifier')
        if user_input:
            selected_user = None
            match = re.search(r'\(([a-f0-9]{8})\)$', user_input)
            
            if match:
                uuid_prefix = match.group(1)
                found_users = User.objects.filter(tracking_cookie__startswith=uuid_prefix)
                if found_users.exists():
                    selected_user = found_users.first()
            
            if selected_user:
                obj.user = selected_user
            else:
                new_name = user_input.strip()
                obj.user = User.objects.create(
                    name=new_name, 
                    initial_ip="127.0.0.1", 
                    initial_user_agent="Admin Panel"
                )
                messages.info(request, f"New user '{new_name}' created.")

        # 2. Generate post_number
        if is_new and not obj.post_number:
            obj.post_number = Post.get_next_post_number()
            if not obj.submission_ip:
                obj.submission_ip = "127.0.0.1" 
                obj.submission_user_agent = "Admin Panel"

        # 3. Handle Relative Scheduling
        delay_hours = form.cleaned_data.get('schedule_delay_hours')
        delay_minutes = form.cleaned_data.get('schedule_delay_minutes')

        if delay_hours or delay_minutes:
            hours = delay_hours or 0
            minutes = delay_minutes or 0
            obj.scheduled_time = timezone.now() + timedelta(hours=hours, minutes=minutes)
            obj.status = Post.PostStatus.SCHEDULED

        # 4. Final Save & Queue
        if obj.scheduled_time:
            obj.status = Post.PostStatus.SCHEDULED
            super().save_model(request, obj, form, change)
            
            # Use on_commit to ensure task only fires after DB commit
            transaction.on_commit(lambda: process_and_publish_post.apply_async(args=[obj.id], eta=obj.scheduled_time))
            
            local_time_str = obj.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')
            messages.success(request, f"Post #{obj.post_number} scheduled for {local_time_str} (Server Time).")
        
        else:
            # Post Now
            if obj.status == Post.PostStatus.PROCESSING or (is_new and obj.status != Post.PostStatus.SCHEDULED):
                obj.status = Post.PostStatus.PROCESSING
                super().save_model(request, obj, form, change)
                
                # FIX: Use on_commit to prevent duplicate/premature firing
                transaction.on_commit(lambda: process_and_publish_post.delay(obj.id))
                
                messages.success(request, f"Post #{obj.post_number} processing now.")
            else:
                super().save_model(request, obj, form, change)

    @admin.display(description='Status', ordering='status')
    def get_status_display_colored(self, obj):
        if obj.status == Post.PostStatus.POSTED:
            color = "green"
        elif obj.status == Post.PostStatus.SCHEDULED:
            color = "purple"
        elif obj.status in [Post.PostStatus.PENDING_MODERATION, Post.PostStatus.AWAITING_PAYMENT]:
            color = "orange"
        elif obj.status == Post.PostStatus.FAILED:
            color = "red"
        else:
            color = "blue"
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())