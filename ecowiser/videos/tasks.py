from celery import shared_task
import subprocess
import boto3
from webvtt import WebVTT
from django.core.files.storage import default_storage
import json
import boto3
from django.conf import settings
from .models import Video

test_ACCESS_KEY_ID = ''
test_SECRET_ACCESS_KEY = ''
AWS_REGION = 'us-west-2'
AWS_STORAGE_BUCKET_NAME = ''



s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID,
                         aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                         region_name=AWS_REGION)


from celery import shared_task
import subprocess
import boto3
from webvtt import WebVTT
from django.core.files.storage import default_storage
import json
import os


@shared_task
def process_video_task(video_name, temp_file_path, video_id):
    video_name_sub = video_name.split('.')[0]

    subtitles_dir = '/tmp/subtitles'
    
    print("before")
    srt_output_path = os.path.join(subtitles_dir, f'{video_name_sub}.srt')
    try:
        subprocess.run(['/app/ccextractor/linux/ccextractor', temp_file_path, '-o', srt_output_path], check=True)
        print("after")
    except subprocess.CalledProcessError as e:
        print(f"Error during subtitle extraction: {e}")
        raise

    input_path = srt_output_path
    output_path = os.path.join(subtitles_dir, f'{video_name_sub}.vtt')
    try:
        captions = WebVTT().from_srt(input_path)
        captions.save(output_path)
        print('Subtitle extraction and conversion done')
    except Exception as e:
        print(f"Error during SRT to VTT conversion: {e}")
        raise

    vtt_file_name = f'{video_name_sub}.vtt'
    
    try:
        
        with open(output_path, 'rb') as vtt_file:
            default_storage.save(vtt_file_name, vtt_file)
        s3_client.upload_file(output_path, AWS_STORAGE_BUCKET_NAME, vtt_file_name)

        pre_signed_url_vtt = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_STORAGE_BUCKET_NAME, 'Key': vtt_file_name},
            ExpiresIn=2592000)
        print(f'Subtitle uploaded to S3: {pre_signed_url_vtt}')
    except Exception as e:
        print(f"Error during S3 upload: {e}")
        raise
    
    try:
        video_file_name = os.path.basename(temp_file_path)
        s3_client.upload_file(temp_file_path, AWS_STORAGE_BUCKET_NAME, video_file_name)

        pre_signed_url_video = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_STORAGE_BUCKET_NAME, 'Key': video_file_name},
            ExpiresIn=2592000)
        print(f'Video uploaded to S3: {pre_signed_url_video}')
    except NoCredentialsError as e:
        print(f"Error during video upload to S3: {e}")
        raise
    

    try:
        subprocess.run(['webvtt-to-json', output_path, '-o', f'{subtitles_dir}/{video_name_sub}.json'], check=True)
        upload_json_to_dynamodb(video_name_sub, video_id, pre_signed_url_video, pre_signed_url_vtt )
        
    except subprocess.CalledProcessError as e:
        print(f"Error during VTT to JSON conversion: {e}")
        raise



def upload_json_to_dynamodb(video_name_sub, video_id, pre_signed_url_video, pre_signed_url_vtt ):
    dynamodb = boto3.resource('dynamodb', aws_access_key_id=AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                              region_name=AWS_REGION)

    table = dynamodb.Table('subtitle') 

    json_file_path = f'/tmp/subtitles/{video_name_sub}.json'
    try:
        if not os.path.exists(json_file_path):
            print(f"JSON file does not exist: {json_file_path}")
            return

        with open(json_file_path, 'r') as json_file:
            subtitles = json.load(json_file)

        print('done', type(subtitles))
        count = 0
        for subtitle in subtitles:
            start = subtitle['start']
            end = subtitle['end']
            lines = '\n'.join(subtitle['lines'])

            count += 1
            try:
                response = table.put_item(
                    Item={
                        'video_name': video_name_sub,
                        'start': start,
                        'end': end,
                        'lines': lines
                    }
                )
                print('vtt input:', count)
            except Exception as e:
                print('Error adding item:', str(e))
        print('done uploading to dynamodb :', response)

        print("video_id",video_id)
        video = Video.objects.get(id=video_id)
        video.video_path = pre_signed_url_video
        video.vtt_path = pre_signed_url_vtt
        video.status = True
        video.save()

    except Exception as e:
        print(f'Error reading JSON file: {e}')

