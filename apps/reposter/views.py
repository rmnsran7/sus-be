from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from celery.result import AsyncResult
from .tasks import repost_to_instagram_task

class ReposterStartView(APIView):
    # We remove the JSON restriction to allow HTML rendering
    def get(self, request):
        link = request.query_params.get('link')
        if not link:
            return render(request, 'reposter/error.html', {"error": "No link provided."})
        
        # Start the background task
        task = repost_to_instagram_task.delay(link)
        
        # Render the interactive processing page, passing the task ID
        return render(request, 'reposter/process.html', {
            "task_id": task.id,
            "target_link": link
        })

class ReposterStatusView(APIView):
    def get(self, request, task_id):
        task_result = AsyncResult(task_id)
        return Response({
            "status": task_result.status,
            "info": task_result.info if task_result.info else {"status": "Waiting..."}
        })