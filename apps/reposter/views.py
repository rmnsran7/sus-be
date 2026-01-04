from rest_framework.views import APIView
from rest_framework.response import Response
from celery.result import AsyncResult
from .tasks import repost_to_instagram_task

class ReposterStartView(APIView):
    def get(self, request):
        link = request.query_params.get('link')
        if not link:
            return Response({"error": "Link parameter is required"}, status=400)
        
        # Start background task
        task = repost_to_instagram_task.delay(link)
        
        return Response({
            "task_id": task.id,
            "status_url": f"/api/reposter/status/{task.id}/"
        })

class ReposterStatusView(APIView):
    def get(self, request, task_id):
        task_result = AsyncResult(task_id)
        result = {
            "task_id": task_id,
            "task_status": task_result.status,
            "task_info": task_result.info,
        }
        return Response(result)