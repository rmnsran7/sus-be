# apps/posts/admin.py

from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
import re  # Used to parse the Name (UUID) format

from .models import Post, PostImage
from .tasks import process_and_publish_post
from apps.users.models import User  # Import User model

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    readonly_fields = ('id', 'image_url', 'is_text_image', 'created_at')
    can_delete = False

# --- Custom Widget for "Select or Type" functionality ---
class DatalistTextInput(forms.TextInput):
    """
    A custom text input that renders a <datalist> for autocomplete suggestions.
    """
    def __init__(self, datalist_options=None, *args, **kwargs):
        self.datalist_options = datalist_options or []
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        datalist_id = f"{name}_list"
        attrs['list'] = datalist_id  # Link input to the datalist ID
        attrs['autocomplete'] = 'off' # Disable browser history autocomplete
        
        text_input_html = super().render(name, value, attrs, renderer)
        
        # Create option tags for the datalist
        options_html = "".join([f'<option value="{opt}">' for opt in self.datalist_options])
        datalist_html = f'<datalist id="{datalist_id}">{options_html}</datalist>'
        
        # Return combined HTML
        return format_html(text_input_html + datalist_html)


# --- Custom Admin Form ---
class PostAdminForm(forms.ModelForm):
    # 1. Streamlined User Field
    user_identifier = forms.CharField(
        label="User (Select or Type New)",
        help_text="Type a name. Select from the dropdown to use an existing user. Type a NEW name to create a new user automatically.",
        required=True,
        widget=forms.TextInput() # Widget is swapped in __init__ to populate data
    )

    # 2. Relative Scheduling Fields
    schedule_delay_hours = forms.IntegerField(
        min_value=0, 
        required=False, 
        label="Post in (Hours)",
        help_text="Delay posting by this many hours."
    )
    schedule_delay_minutes = forms.IntegerField(
        min_value=0, 
        required=False, 
        label="Post in (Minutes)",
        help_text="Delay posting by this many minutes."
    )

    class Meta:
        model = Post
        fields = '__all__'
        exclude = ('user',)  # We exclude the strict ForeignKey field to handle it manually

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-fill user_identifier if editing an existing post
        if self.instance.pk and self.instance.user:
            self.fields['user_identifier'].initial = str(self.instance.user)
        
        # Populate the datalist with recent users (Limit to 100 for performance)
        # We sort by 'last_seen_at' so the most active users appear first.
        recent_users = User.objects.all().order_by('-last_seen_at')[:100]
        user_options = [str(u) for u in recent_users]
        
        # Assign the custom widget with the fetched options
        self.fields['user_identifier'].widget = DatalistTextInput(datalist_options=user_options)


@admin.action(description="🔄 Retry publishing selected posts")
def retry_failed_posts(modeladmin, request, queryset):
    count = 0
    for post in queryset:
        if post.status not in [Post.PostStatus.POSTED, Post.PostStatus.PROCESSING]:
            post.status = Post.PostStatus.PROCESSING
            post.meta_api_error = None
            post.save()
            process_and_publish_post.delay(post.id)
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
    
    # Removed autocomplete_fields=['user'] because we are using the custom user_identifier
    
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
            'description': "Enter the username and message. New users are created automatically.",
            'fields': ('user_identifier', 'text_content')
        }),
        ('Publishing Options', {
            'description': "Use 'Post in...' to schedule relative to now (Server Time).",
            'fields': (
                'status', 
                ('schedule_delay_hours', 'schedule_delay_minutes'),
                'scheduled_time'
            )
        }),
        ('System Details (Read-Only)', {
            'classes': ('collapse',),
            'fields': ('post_number', 'moderation_reason', 'meta_api_status', 'meta_api_error', 'instagram_media_id', 'created_at', 'posted_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Custom save logic to handle 'Streamlined User Creation' and 'Relative Scheduling'.
        """
        is_new = obj.pk is None
        
        # --- 1. Handle User Resolution ---
        user_input = form.cleaned_data.get('user_identifier')
        
        if user_input:
            selected_user = None
            
            # The __str__ method of User is: Name (UUID_Prefix)
            # We use Regex to check if the input matches this format to find an existing user
            # Regex looks for: anything + space + ( + 8 chars of hex + ) at the end of string
            match = re.search(r'\(([a-f0-9]{8})\)$', user_input)
            
            if match:
                uuid_prefix = match.group(1)
                # Try to find the user by this UUID prefix
                found_users = User.objects.filter(tracking_cookie__startswith=uuid_prefix)
                if found_users.exists():
                    selected_user = found_users.first()
            
            if selected_user:
                # User selected from list
                obj.user = selected_user
            else:
                # Input didn't match an existing ID, so we create a NEW USER
                # We strip potential whitespace
                new_name = user_input.strip()
                obj.user = User.objects.create(
                    name=new_name, 
                    initial_ip="127.0.0.1", 
                    initial_user_agent="Admin Panel"
                )
                messages.info(request, f"New user '{new_name}' was automatically created.")


        # --- 2. Generate post_number if new ---
        if is_new and not obj.post_number:
            obj.post_number = Post.get_next_post_number()
            if not obj.submission_ip:
                obj.submission_ip = "127.0.0.1" 
                obj.submission_user_agent = "Admin Panel"

        # --- 3. Handle Relative Scheduling Logic ---
        delay_hours = form.cleaned_data.get('schedule_delay_hours')
        delay_minutes = form.cleaned_data.get('schedule_delay_minutes')

        if delay_hours or delay_minutes:
            hours = delay_hours or 0
            minutes = delay_minutes or 0
            future_time = timezone.now() + timedelta(hours=hours, minutes=minutes)
            obj.scheduled_time = future_time
            obj.status = Post.PostStatus.SCHEDULED

        # --- 4. Final Save & Task Queueing ---
        if obj.scheduled_time:
            # Force status to SCHEDULED if time is present
            obj.status = Post.PostStatus.SCHEDULED
            super().save_model(request, obj, form, change)
            
            # Queue with ETA
            process_and_publish_post.apply_async(args=[obj.id], eta=obj.scheduled_time)
            
            local_time_str = obj.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')
            messages.success(request, f"Post #{obj.post_number} scheduled for {local_time_str} (Server Time).")
        
        else:
            # Post Now Logic
            if obj.status == Post.PostStatus.PROCESSING or (is_new and obj.status != Post.PostStatus.SCHEDULED):
                obj.status = Post.PostStatus.PROCESSING
                super().save_model(request, obj, form, change)
                
                # Queue immediately
                process_and_publish_post.delay(obj.id)
                messages.success(request, f"Post #{obj.post_number} is being processed now.")
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