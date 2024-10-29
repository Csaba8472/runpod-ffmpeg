""" Example handler file. """

import runpod
import ffmpeg
import os, subprocess

from runpod.serverless.utils import download_files_from_urls, rp_cleanup, rp_debugger
from runpod.serverless.utils import upload_file_to_bucket


# If your handler runs inference on a model, load the model here.
# You will want models to be loaded into memory before starting serverless.

WATERMARK_MARGIN = 0.015 # Margin in percentage of the videos width
WATERMARK_SCALE = 0.3 # Width of the watermark in the percentage of the video
WATERMARK_WIDTH = 1142 # Width of the watermark
WATERMARK_HEIGHT = 408 # Height of the watermark

watermark_image = 'watermark.png'

def process(input_video: str, output_video: str, watermark_image: str):

    input_stream = ffmpeg.input(input_video, hwaccel='cuda')
    video_stream = input_stream.video
    audio_stream = input_stream.audio

    # First, get video dimensions (width, height)
    probe = ffmpeg.probe(input_video)
    video_info = next(input_stream for input_stream in probe['streams'] if input_stream['codec_type'] == 'video')
    video_width = int(video_info['width'])
    video_height = int(video_info['height'])

    aspect_ratio = WATERMARK_WIDTH / WATERMARK_HEIGHT

    # Calculate scaled watermark dimensions
    watermark_scaled_width = int(WATERMARK_SCALE * video_width)

    # Calculate watermark position for bottom-right placement with margin
    translate_x = int(video_width - watermark_scaled_width - (WATERMARK_MARGIN * video_width))  # X position from the right
    translate_y = int(video_height - watermark_scaled_width / aspect_ratio - (WATERMARK_MARGIN * video_width))  # Y position from the bottom

    video_stream = video_stream.overlay(
        ffmpeg.input(watermark_image)
        .filter('scale', watermark_scaled_width, watermark_scaled_width / aspect_ratio),
        x=translate_x, 
        y=translate_y
    )

    output_stream = ffmpeg.output(video_stream, audio_stream, output_video, vcodec='h264_nvenc', acodec='aac')

    # Run the ffmpeg process
    try:
        output_stream.run(overwrite_output=True, quiet=True)
    except ffmpeg.Error as e:
        print('FFmpeg Error:', e.stderr.decode('utf-8'))
        raise Exception("Failed to process video stream") from e


def process_cli(input_video: str, output_video: str, watermark_image: str):
    process = subprocess.Popen(
        [
            'ffmpeg',
            '-i', input_video,
            '-i', watermark_image,
            '-filter_complex', 'overlay=main_w-overlay_w-10:main_h-overlay_h-10',
            '-codec:a', 'copy',
            output_video
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )

    while True:
        line = process.stdout.readline()
        if line:
            print(line, end='')
        elif process.poll() is not None:
            break
    
    if process.returncode != 0:
        raise Exception("FFmpeg command failed")



def handler(job):
    """ Handler function that will be used to process jobs. """
    job_input = job['input']

    name = job_input.get('name', 'World')

    print(name)

    # Define the file name and file location
    file_name = 'output.mp4'
    file_location = 'output.mp4'

    print(name)
    
    video_input = download_files_from_urls(job['id'], [job_input['video']])[0]
    
    print(name)

    process(video_input, file_name, watermark_image)

    # Upload the file and get the presigned URL
    presigned_url = upload_file_to_bucket(file_name, file_location)

    # Print the presigned URL
    print(f"Presigned URL: {presigned_url}")

    return f"URL: {presigned_url}!"


runpod.serverless.start({"handler": handler})

#if __name__ == "__main__":
#    process("input.mp4", "output23.mp4", "watermark.png")