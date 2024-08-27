import argparse
import json
import logging
import os
import re
import sys

import requests

from album_manager_googlephotos.google_helper import get_authenticated_photos_library_service

logger = logging.getLogger(__name__)

MEDIA_ITEMS_FILE = 'media_items.json'
ALBUMS_FILE = 'albums.json'


def create_argument_parser():
    parser = argparse.ArgumentParser(
        description='Replicates local folder structure as Albums in Google Photos',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('--local_album_path', help='Path to local folder containing albums.', dest='local_album_path',
                        required=True)
    parser.add_argument('--folder_prefix',
                        help='Folder prefix filtering. eg 2004 will sync just folders starting with 2004.',
                        dest='folder_prefix')
    parser.add_argument('--verbose', help='Detailed output about progress', dest='verbose', action='store_true')
    parser.add_argument('--refresh_media_items', help='Download and store media items from google photos',
                        dest='refresh_media_items', action='store_true')
    parser.add_argument('--refresh_albums', help='Download and store albums info from google photos',
                        dest='refresh_albums', action='store_true')
    parser.add_argument('--monthly_albums',
                        help='Folder names containing albums follows YYYY-MM  pattern. Media items in subfolders will '
                             'be assigned to first parent following pattern. Otherwise albums will be named as folder '
                             'containing media items.',
                        dest='monthly_albums', default=True, action=argparse.BooleanOptionalAction)

    return parser


def download_media_items(service):
    media_items = []
    page_token = None
    while True:
        result = service.mediaItems().list(pageSize=100, pageToken=page_token).execute()
        if 'mediaItems' in result:
            logger.debug('Got media items from Google Photos: %s', len(result['mediaItems']))
            for item in result['mediaItems']:
                media_items.append({'id': item['id'], 'filename': item['filename']})
        if 'nextPageToken' in result:
            page_token = result['nextPageToken']
        else:
            page_token = None
        if page_token is None:
            break
    return media_items


def download_albums_info(service):
    albums_info = []
    page_token = None
    while True:
        result = service.albums().list(pageSize=50, pageToken=page_token).execute()
        if 'albums' in result:
            logger.debug('Got albums from Google Photos: %s', len(result['albums']))
            for album in result['albums']:
                albums_info.append(album)
        if 'nextPageToken' in result:
            page_token = result['nextPageToken']
        else:
            page_token = None
        if page_token is None:
            break
    return albums_info


def filter_media_items(filenames):
    filtered_filenames = []
    photo_types = ['AVIF', 'BMP', 'GIF', 'HEIC', 'ICO', 'JPG', 'JPEG', 'PNG', 'TIFF', 'WEBP']
    video_types = ['3GP', '3G2', 'ASF', 'AVI', 'DIVX', 'M2T', 'M2TS', 'M4V', 'MKV', 'MMV', 'MOD', 'MOV', 'MP4', 'MPG',
                   'MTS', 'TOD', 'WMV']
    for filename in filenames:
        file_type = filename.split('.')[-1]
        if file_type.upper() in photo_types:
            filtered_filenames.append(filename)
        if file_type.upper() in video_types:
            filtered_filenames.append(filename)
    return filtered_filenames


def get_local_albums(local_album_path, monthly_albums, folder_prefix):
    local_albums = {}
    for (dirpath, dirnames, filenames) in os.walk(local_album_path):
        if local_album_path + '/' + folder_prefix not in dirpath:
            continue
        filtered_filenames = filter_media_items(filenames)
        if len(filtered_filenames) == 0:
            # not a folder containing media items, nothing to add
            continue
        target_album = None
        for album in local_albums:
            if album in dirpath:
                target_album = album
                break
        if not target_album:
            if monthly_albums:
                for dir_name in reversed(dirpath.split('/')):
                    target_album = dir_name
                    if re.match("\\d{4}-\\d{0,2}", target_album):
                        break
            else:
                target_album = dirpath.split('/')[-1]
            local_albums[target_album] = []
        local_albums[target_album].extend(
            [{"filename": target_album + '_' + f, "filepath": dirpath + '/' + f} for f in filtered_filenames])
    return local_albums


def get_album_id(local_album, google_photos_albums):
    for album in google_photos_albums:
        if local_album == album['title']:
            return album['id']
    return None


def create_google_photos_album(service, local_album_name):
    return service.albums().create(body={"album": {"title": local_album_name}}).execute()


def get_album_media_items(service, local_files, media_items):
    media_item_ids = []
    needs_upload = []
    for local_file in local_files:
        media_item_id = None
        for media_item in media_items:
            if media_item['filename'] == local_file['filename']:
                media_item_id = media_item['id']
                break
        if not media_item_id:
            # logger.error('Could not find media item for %s', local_file)
            needs_upload.append(local_file)
        else:
            media_item_ids.append(media_item_id)

    upload_tokens = []
    for media_upload in needs_upload:
        with open(media_upload["filepath"], "rb") as f:
            media_contents = f.read()
        if service._http.credentials.expired:
            service = get_authenticated_photos_library_service()
        headers = {
            'Content-Type': "application/octet-stream",
            'X-Goog-Upload-File-Name': media_upload["filename"].encode('utf8'),
            'X-Goog-Upload-Protocol': "raw",
            'Authorization': "Bearer " + service._http.credentials.token,
        }
        token = requests.post('https://photoslibrary.googleapis.com/v1/uploads',
                              headers=headers, data=media_contents).text
        upload_tokens.append({
            "simpleMediaItem": {
                "uploadToken": token,
                "fileName": media_upload["filename"]
            }
        })
        logger.info(f"Uploaded {media_upload['filename']}.")
    for batch in [upload_tokens[i:i + 50] for i in range(0, len(upload_tokens), 50)]:
        logger.info(f"Adding {len(batch)} media items to Google Photos.")
        result = service.mediaItems().batchCreate(body={"newMediaItems": batch}).execute()
        for new_media_item in result['newMediaItemResults']:
            media_item_ids.append(new_media_item["mediaItem"]["id"])
            media_items.append(
                {"id": new_media_item["mediaItem"]["id"],
                 "filename": new_media_item["mediaItem"]["filename"]
                 })

    return media_item_ids


def main():
    parsed_args = create_argument_parser().parse_args()
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if parsed_args.verbose else logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    service = None
    if parsed_args.refresh_media_items or not os.path.isfile(MEDIA_ITEMS_FILE):
        logger.info('Downloading media items from Google Photos')
        service = get_authenticated_photos_library_service(service)
        media_items = download_media_items(service)
    else:
        logger.info('Loading media items from local file')
        with open(MEDIA_ITEMS_FILE, 'r', encoding='utf-8') as f:
            media_items = json.load(f)

    if parsed_args.refresh_albums or not os.path.isfile(ALBUMS_FILE):
        logger.info('Downloading albums info from Google Photos')
        service = get_authenticated_photos_library_service(service)
        google_photos_albums = download_albums_info(service)
    else:
        logger.info('Loading albums info from local file')
        with open(ALBUMS_FILE, 'r', encoding='utf-8') as f:
            google_photos_albums = json.load(f)

    local_albums = get_local_albums(parsed_args.local_album_path, parsed_args.monthly_albums, parsed_args.folder_prefix)
    logger.info("Find %d local albums", len(local_albums))

    service = get_authenticated_photos_library_service(service)
    for local_album in local_albums:
        logger.info("Processing folder %s", local_album)
        album_id = get_album_id(local_album, google_photos_albums)
        save(google_photos_albums, media_items)
        if not album_id:
            logger.info("Creating Google Photos Album %s", local_album)
            crated_album = create_google_photos_album(service, local_album)
            album_id = crated_album['id']
            google_photos_albums.append(crated_album)
        media_item_ids = get_album_media_items(service, local_albums[local_album], media_items)
        save(google_photos_albums, media_items)
        logger.debug("Adding %d media items to Google Photos Album %s", len(media_item_ids), local_album)
        # add media items to album in batch
        for batch in [media_item_ids[i:i + 50] for i in range(0, len(media_item_ids), 50)]:
            result = service.albums().batchAddMediaItems(albumId=album_id,
                                                         body={"mediaItemIds": [i for i in set(batch)]}).execute()


def save(google_photos_albums, media_items):
    with open(MEDIA_ITEMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(media_items, f, ensure_ascii=False, indent=4)
    with open(ALBUMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(google_photos_albums, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
