import os
import requests
import arrow
from isoduration import parse_duration
from datetime import timedelta
from flask import Flask, render_template, request
from googleapiclient.discovery import build
import googleapiclient.discovery

API_KEY = os.getenv("SECRET_API_KEY")
youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=API_KEY)

app = Flask(__name__)

def is_short(video_id):
    url = f"https://www.youtube.com/shorts/{video_id}"
    response = requests.head(url, allow_redirects=False)
    return response.status_code == 200


def format_big_numbers(count):
    count = int(count)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return str(count)
    

def parse_date(date):
    past_date = arrow.get(date)
    return past_date.humanize(locale='pt-br')

def convert_duration(iso_duration):
    
    duration = parse_duration(iso_duration)

    # Convert the duration to a timedelta object
    td = timedelta(
        hours=float(duration.time.hours),
        minutes=float(duration.time.minutes),
        seconds=float(duration.time.seconds)
    )

    return td


@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


@app.route('/results', methods=['GET', 'POST'])
def results():
    user_search = request.form.get('search')

    # Contains multiple rows each with a channel id, sub count, title, 
    # and avatar respectively, that was retrieved in the channel request area
    channel_matrix = []

    # Contains multiple rows each with a video id, thumbnail, title, 
    # and date published respectively, that was retrieved in the video request area
    video_matrix = []

    # Contains every video id retrieved
    videos_and_shorts = []

    channel_matrix.clear()
    video_matrix.clear()

    next_page_token = None

    switch_to_channel_or_video = request.form.get('change-btn')
      
# Channel request area
    if switch_to_channel_or_video == 'channel-btn':

        # Constains every channel id retrieved below
        channel_search_id_list = []

        search_channel_data_request = youtube.search().list(
            part='snippet',
            q=user_search,
            type='channel',
            maxResults=10
        )        

        search_channel_data_response = search_channel_data_request.execute()

        for item in search_channel_data_response['items']:
            channel_search_id_list.append(item['id']['channelId'])

        for ch_id in channel_search_id_list:
            channel_data_request = youtube.channels().list(
                part='snippet',
                id=ch_id
            )

            channel_subscriber_request = youtube.channels().list(
                part='statistics',
                id=ch_id
            )
            
            channel_data_response = channel_data_request.execute()
            channel_subscriber_response = channel_subscriber_request.execute()
            
            channel_title = channel_data_response['items'][0]['snippet']['title']

            get_thumbnails = channel_data_response['items'][0]['snippet']['thumbnails']
            ch_avatar_url = get_thumbnails.get('medium')['url']

            channel_subscriber_count = channel_subscriber_response['items'][0]['statistics']['subscriberCount']

            channel_id = channel_subscriber_response['items'][0]['id']

            row = []
            row.extend([channel_id, format_big_numbers(channel_subscriber_count), channel_title, ch_avatar_url])
            channel_matrix.append(row)

        return render_template('results.html', channel_matrix=channel_matrix)
    
# Video request area
    else:
        relevant_video_request = youtube.search().list(
            part='snippet',
            q=user_search,
            type='video',
            pageToken=next_page_token,
            order='relevance',
            maxResults=10
        )

        relevant_video_response = relevant_video_request.execute()

        # If the video is not a short add it to the list
        for item in relevant_video_response['items']:
            if not is_short(item['id']['videoId']):
                videos_and_shorts.append(item['id']['videoId'])

        next_page_token = relevant_video_response.get('nextPageToken')
        if not next_page_token:
            pass


    for videoid in videos_and_shorts:
        video_data_request = youtube.videos().list(
            part='snippet',
            id=videoid
        )

        video_view_count_request = youtube.videos().list(
            part='statistics',
            id=videoid
        )

        video_view_count_response = video_view_count_request.execute()

        video_data_response = video_data_request.execute()
        # Retrieves the video title, date published, and thumbnail respectively
        title = video_data_response['items'][0]['snippet']['title']
        date_published = parse_date(video_data_response['items'][0]['snippet']['publishedAt'])
        thumbnails = video_data_response['items'][0]['snippet']['thumbnails']
        thumbnail_url = thumbnails.get('medium')['url']
        video_view_count = format_big_numbers(video_view_count_response['items'][0]['statistics']['viewCount'])

        row = []
        row.extend([videoid, thumbnail_url, title, date_published, video_view_count])
        video_matrix.append(row)

    return render_template('results.html', video_matrix=video_matrix)


@app.route('/<ch_id>/videos', methods=['GET', 'POST'])
def videos(ch_id):

    next_page_token = None

    # used for storing many videos and shorts ids that will be going into 
    # different rows in the ch_video_matrix so every video and shorts has its respective titles etc.
    videos_and_shorts = []

    ch_video_matrix = []
    ch_video_matrix.clear()

    ch_data_request = youtube.channels().list(
        part='snippet',
        id=ch_id
    )

    ch_subscriber_request = youtube.channels().list(
        part='statistics',
        id=ch_id
    )

    ch_data_response = ch_data_request.execute()
    ch_subscriber_response = ch_subscriber_request.execute()

    # Retrieves the channel title, thumbnail, sub count, and custom url (@Ch_Name) respectively.
    channel_title = ch_data_response['items'][0]['snippet']['title']
    get_thumbnails = ch_data_response['items'][0]['snippet']['thumbnails']
    ch_thumbnail_url = get_thumbnails.get('medium')['url']
    ch_subscriber_count = ch_subscriber_response['items'][0]['statistics']['subscriberCount']
    ch_custom_url = ch_data_response['items'][0]['snippet']['customUrl']

    # Looks for completed broadcasts in the channel (does not contain videos)
    ch_content_request = youtube.search().list(
        part='snippet',
        channelId=ch_id,
        type='video',
        order='date',
        maxResults=10,
        pageToken=next_page_token
    )
    ch_content_response = ch_content_request.execute()

    next_page_token = ch_content_response.get('nextPageToken')
    if not next_page_token:
        pass

    # for content_id in ch_content_response check if the id has something inside liveStreamingDetails if so its a stream
    for content_id in ch_content_response['items']:
        content_request = youtube.videos().list(
            part='liveStreamingDetails',
            id=content_id['id']['videoId'],
        )
        content_response = content_request.execute()

        video_details = content_response['items'][0].get('liveStreamingDetails', {})
        video_id = content_response['items'][0]['id']
        scheduled_start_time = video_details.get('scheduledStartTime')

        if not scheduled_start_time: 
            videos_and_shorts.append(video_id)

    for content_id in videos_and_shorts:
        video_data_request = youtube.videos().list(
            part='snippet',
            id=content_id
        )

        video_view_count_request = youtube.videos().list(
            part='statistics',
            id=content_id
        )

        duration_request = youtube.videos().list(
            part='contentDetails',
            id=content_id
        )

        duration_response = duration_request.execute()
        video_view_count_response = video_view_count_request.execute()
        video_data_response = video_data_request.execute()

        # Retrieves the video id, title, date published, duration, and thumbnail respectively
        video_title = video_data_response['items'][0]['snippet']['title']
        date_published = parse_date(video_data_response['items'][0]['snippet']['publishedAt'])
        vid_thumbnails_get = video_data_response['items'][0]['snippet']['thumbnails']
        thumbnail_url = vid_thumbnails_get.get('medium')['url']
        video_view_count = format_big_numbers(video_view_count_response['items'][0]['statistics']['viewCount'])
        video_duration = convert_duration(duration_response['items'][0]['contentDetails']['duration'])

        row = []
        row.extend([content_id, video_title, date_published, thumbnail_url, video_view_count, video_duration])
        ch_video_matrix.append(row)

    return render_template('videos.html', ch_id=ch_id, channel_title=channel_title,
                           ch_thumbnail_url=ch_thumbnail_url,
                           ch_subscriber_count=format_big_numbers(ch_subscriber_count),
                           ch_custom_url=ch_custom_url, ch_video_matrix=ch_video_matrix)


@app.route('/<ch_id>/Ao_Vivo', methods=['GET', 'POST'])
def streams(ch_id):

    next_page_token = None
    # contains multiple rows of completed, upcoming, and currently live strems, each with information about completed and live broadcasts retrieved below
    ch_clive_matrix = []
    ch_ulive_matrix = []
    ch_live_matrix = []

    ch_ulive_matrix.clear()
    ch_live_matrix.clear()
    ch_clive_matrix.clear()

    # Contains completed streams, live streams, and upcoming live streams
    complete_broadcasts = []
    live_broadcasts = []
    up_broadcasts = []

    ch_data_request = youtube.channels().list(
        part='snippet',
        id=ch_id
    )

    ch_subscriber_request = youtube.channels().list(
        part='statistics',
        id=ch_id
    )

    ch_data_response = ch_data_request.execute()
    ch_subscriber_response = ch_subscriber_request.execute()

    # Retrieves the channel title, thumbnail, sub count, and custom url (@Ch_Name) respectively.
    channel_title = ch_data_response['items'][0]['snippet']['title']
    get_thumbnails = ch_data_response['items'][0]['snippet']['thumbnails']
    ch_thumbnail_url = get_thumbnails.get('medium')['url']
    ch_subscriber_count = ch_subscriber_response['items'][0]['statistics']['subscriberCount']
    ch_custom_url = ch_data_response['items'][0]['snippet']['customUrl']

    # Looks for liveStreamingDetails of an id
    ch_content_request = youtube.search().list(
        part='snippet',
        channelId=ch_id,
        type='video',
        order='date',
        maxResults=10,
        pageToken=next_page_token
    )

    ch_content_response = ch_content_request.execute()

    next_page_token = ch_content_response.get('nextPageToken')
    if not next_page_token:
        pass

    # for content_id in ch_content_response check if the id has something inside liveStreamingDetails if so its a stream
    for content_id in ch_content_response['items']:
        if not is_short(content_id['id']['videoId']):
            content_request = youtube.videos().list(
                part='liveStreamingDetails',
                id=content_id['id']['videoId'],
            )
            content_response = content_request.execute()

            live_details = content_response['items'][0].get('liveStreamingDetails', {})
            actual_start_time = live_details.get('actualStartTime')
            actual_end_time = live_details.get('actualEndTime')
            scheduled_start_time = live_details.get('scheduledStartTime')
            # for item_id retrieved in ch_clive_response add it to the lc_broadcasts list
            if actual_end_time:
                complete_broadcasts.append(content_response['items'][0]['id'])

            elif actual_start_time:
                live_broadcasts.append(content_response['items'][0]['id'])
            
            elif scheduled_start_time and not actual_start_time:
                up_broadcasts.append(content_response['items'][0]['id'])

    print(up_broadcasts)

    # Retrieves data for upcoming broadcasts
    for content_id in up_broadcasts:
        stream_data_request = youtube.videos().list(
            part='snippet',
            id=content_id
        )

        stream_view_count_request = youtube.videos().list(
            part='statistics',
            id=content_id
        )

        stream_start_time_request = youtube.videos().list(
            part='liveStreamingDetails',
            id=content_id
        )

        stream_data_response = stream_data_request.execute()
        stream_view_count_response = stream_view_count_request.execute()
        stream_start_time_response = stream_start_time_request.execute()

        # Retrieves the video id, title, date published, and thumbnail respectively
        stream_title = stream_data_response['items'][0]['snippet']['title']
        start_time = parse_date(stream_start_time_response['items'][0]['liveStreamingDetails']['scheduledStartTime'])
        stream_thumbnails_get = stream_data_response['items'][0]['snippet']['thumbnails']
        thumbnail_url = stream_thumbnails_get.get('medium')['url']
        
        row_up = []
        row_up.extend([content_id, stream_title, start_time, thumbnail_url])
        ch_ulive_matrix.append(row_up)


    # Retrieves data for completed broadcasts
    for content_id in complete_broadcasts:
        stream_data_request = youtube.videos().list(
            part='snippet',
            id=content_id
        )

        stream_view_count_request = youtube.videos().list(
            part='statistics',
            id=content_id
        )

        duration_request = youtube.videos().list(
            part='contentDetails',
            id=content_id
        )

        stream_data_response = stream_data_request.execute()
        stream_view_count_response = stream_view_count_request.execute()
        duration_response = duration_request.execute()

        # Retrieves the video id, title, date published, and thumbnail respectively
        stream_title = stream_data_response['items'][0]['snippet']['title']
        date_published = parse_date(stream_data_response['items'][0]['snippet']['publishedAt'])
        stream_thumbnails_get = stream_data_response['items'][0]['snippet']['thumbnails']
        thumbnail_url = stream_thumbnails_get.get('medium')['url']
        stream_view_count = format_big_numbers(stream_view_count_response['items'][0]['statistics']['viewCount'])
        duration = convert_duration(duration_response['items'][0]['contentDetails']['duration'])

        row_complete = []
        row_complete.extend([content_id, stream_title, date_published, thumbnail_url, stream_view_count, duration])
        ch_clive_matrix.append(row_complete)


    # Retrieves data for live broadcasts
    for content_id in live_broadcasts:
        stream_data_request = youtube.videos().list(
            part='snippet',
            id=content_id
        )

        stream_view_count_request = youtube.videos().list(
            part='statistics',
            id=content_id
        )

        stream_data_response = stream_data_request.execute()
        stream_view_count_response = stream_view_count_request.execute()

        # Retrieves the video id, title, date published, and thumbnail respectively
        stream_title = stream_data_response['items'][0]['snippet']['title']
        date_published = parse_date(stream_data_response['items'][0]['snippet']['publishedAt'])
        stream_thumbnails_get = stream_data_response['items'][0]['snippet']['thumbnails']
        thumbnail_url = stream_thumbnails_get.get('medium')['url']
        stream_view_count = format_big_numbers(stream_view_count_response['items'][0]['statistics']['viewCount'])
        
        row_live = []
        row_live.extend([content_id, stream_title, date_published, thumbnail_url, stream_view_count])
        ch_live_matrix.append(row_live)

    return render_template('streams.html', ch_id=ch_id, channel_title=channel_title,
                           ch_thumbnail_url=ch_thumbnail_url,
                           ch_subscriber_count=format_big_numbers(ch_subscriber_count),
                           ch_custom_url=ch_custom_url, ch_ulive_matrix=ch_ulive_matrix,
                           ch_clive_matrix=ch_clive_matrix, ch_live_matrix=ch_live_matrix)




if __name__ == '__main__':
    app.run(debug=True)