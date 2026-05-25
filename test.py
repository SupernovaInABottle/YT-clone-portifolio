import os
import requests
import arrow
import humanize
from flask import Flask, render_template, request, url_for
from googleapiclient.discovery import build
import googleapiclient.discovery

API_KEY = os.getenv("API_KEY")
youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=API_KEY)

app = Flask(__name__)


def is_short(video_id):
    url = f"https://www.youtube.com/shorts/{video_id}"
    response = requests.head(url, allow_redirects=False)
    return response.status_code == 200


def format_subscribers(count):
    count = int(count)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return str(count)
    

def parse_date(date):
    past_date = arrow.get(date)
    return past_date.humanize()


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
    non_short_videos = []

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
            row.extend([channel_id, format_subscribers(channel_subscriber_count), channel_title, ch_avatar_url])
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
                non_short_videos.append(item['id']['videoId'])

        next_page_token = relevant_video_response.get('nextPageToken')
        if not next_page_token:
            pass


    for videoid in non_short_videos:
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
        video_view_count = humanize.intword(video_view_count_response['items'][0]['statistics']['viewCount'])

        row = []
        row.extend([videoid, thumbnail_url, title, date_published, video_view_count])
        video_matrix.append(row)

    return render_template('results.html', video_matrix=video_matrix)


@app.route('/channel/<ch_id>', methods=['GET', 'POST'])
def channel(ch_id):

    next_page_token = None
    # contains multiple rows, each with information about completed broadcasts retrieved below
    ch_clive_matrix = []
    ch_clive_matrix.clear()

    # contains multiple rows, each with information about videos retrieved below
    ch_video_matrix = []
    ch_video_matrix.clear()

    non_short_videos = []

    ch_data_request = youtube.channels().list(
        part='snippet',
        id=ch_id,
        pageToken=next_page_token,
    )

    ch_subscriber_request = youtube.channels().list(
        part='statistics',
        id=ch_id,
        pageToken=next_page_token,
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
    ch_clive_request = youtube.search().list(
        part='snippet',
        channelId=ch_id,
        type='video',
        eventType='completed',
        order='date',
        maxResults=20
    )

    # Looks for every video in the channel (also contains completed broadcasts)
    ch_video_request = youtube.search().list(
        part='snippet',
        channelId=ch_id,
        type='video',
        order='date',
        maxResults=20
    )

    ch_clive_response = ch_clive_request.execute()
    ch_video_response = ch_video_request.execute()

    # If the content_id is not a completed broadcast or a short then append it to the non_short_videos list
    for vid_id in ch_clive_response['items']:
        if vid_id['id']['videoId'] not in ch_video_response['items'][0]['id']['videoId'] and not is_short(vid_id['id']['videoId']):
            non_short_videos.append(vid_id['id']['videoId'])

    next_page_token = ch_video_response.get('nextPageToken')
    if not next_page_token:
        pass

    for content_id in non_short_videos:
        video_data_request = youtube.videos().list(
            part='snippet',
            id=content_id
        )

        video_view_count_request = youtube.videos().list(
            part='statistics',
            id=content_id
        )

        video_view_count_response = video_view_count_request.execute()
        video_data_response = video_data_request.execute()

        # Retrieves the video id, title, date published, and thumbnail respectively
        video_title = video_data_response['items'][0]['snippet']['title']
        date_published = parse_date(video_data_response['items'][0]['snippet']['publishedAt'])
        vid_thumbnails_get = video_data_response['items'][0]['snippet']['thumbnails']
        thumbnail_url = vid_thumbnails_get.get('medium')['url']
        video_view_count = humanize.intword(video_view_count_response['items'][0]['statistics']['viewCount'])
        
        row = []
        row.extend([content_id, video_title, date_published, thumbnail_url, video_view_count])
        ch_video_matrix.append(row)

    return render_template('channel.html', channel_title=channel_title,
                           ch_thumbnail_url=ch_thumbnail_url,
                           ch_subscriber_count=format_subscribers(ch_subscriber_count),
                           ch_custom_url=ch_custom_url, ch_video_matrix=ch_video_matrix)


if __name__ == '__main__':
    app.run(debug=True)