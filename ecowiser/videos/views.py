
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse 
from .forms import VideoUploadForm
from .tasks import process_video_task
from django.http import JsonResponse
import tempfile
from .models import Video
from django.contrib.auth.decorators import login_required

from django.views.decorators.csrf import csrf_exempt
from boto3.dynamodb.conditions import Key, Attr
import boto3


def upload_video(request):
    form = VideoUploadForm()
    return render(request, 'videos/upload.html', {'form': form})

@login_required
def process_video(request):
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = request.FILES['video']
            video_name = video.name

            tmp_dir = '/tmp'
            with tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False, suffix='.mp4') as temp_file:
                for chunk in video.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            

            video_record = Video.objects.create(
                user=request.user,
                title=video_name,
                video_path=None, 
                vtt_path=None,   
                status=False  
            )

            print("video record",video_record)

            video_id = video_record.id
            print("video id", video_id)
            task = process_video_task.delay(video_name, temp_file_path, video_id)
            request.session['task_id'] = task.id

            return redirect(reverse('videos:video_search') + f'?video_id={video_id}')
    else:
        form = VideoUploadForm()

    return render(request, 'videos/upload.html', {'form': form})





@csrf_exempt
def video_search(request):
    video_id = request.GET.get('video_id')
    
    video = get_object_or_404(Video, id=video_id)

    video_name = video.title.replace('.mp4', '')

    context = {
        'video_file': video.video_path,
        'sub': video.vtt_path,
        'video_id': video_id
    }


    if not video.status:
        return render(request, 'videos/video_in_progress.html', {'video_id': video_id})


    if request.method == 'POST':
        search_query = request.POST.get('search')

        dynamodb = boto3.resource(
            'dynamodb',
            test_access_key_id='',
            test_secret_access_key='',
            region_name='us-west-2'
        )

        table = dynamodb.Table('subtitle')
        

        print("search query ",search_query, video_name )
        

        response = table.query(
            KeyConditionExpression=Key('video_name').eq(video_name),
            FilterExpression=Attr('lines').contains(search_query.strip())
        )

        print("responce",response)

        search_results = response.get('Items', [])

        print("responce ", search_results)

        context['results'] = search_results
        context['search_query'] = search_query

    return render(request, 'videos/video_complete.html', context)


@login_required
def history(request):
    user_videos = Video.objects.filter(user=request.user)

    return render(request, 'videos/history.html', {'results': user_videos})
