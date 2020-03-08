import asyncio
import os
import logging
import argparse
from functools import partial

from aiohttp import web
from aiohttp.web import HTTPNotFound
import aiofiles


DEFAULT_PHOTOS_PATH = 'test_photos'
DEFAULT_DELAY = 0


parser = argparse.ArgumentParser(description='Script runs server for downloading photo archives')
parser.add_argument('--logging',
                    action='store_true',
                    default=None,
                    help='activate logging',
                    )
parser.add_argument('--photos_path',
                    type=str,
                    default=None,
                    help='custom path (str) for main photo directory; default=\'./test_photos\'',
                    )
parser.add_argument('--delay',
                    type=int,
                    default=None,
                    help='custom delay (seconds, int) for download response; default=0',
                    )


def write_log(message):
    if os.getenv('LOGGING_ACTIVE'):
        logging.info(message)


async def get_process(cmd):
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    return process


async def archivate(photos_path, delay, request):
    if not photos_path:
        photos_path = DEFAULT_PHOTOS_PATH
    if not delay:
        delay = DEFAULT_DELAY

    archive_hash = request.match_info['archive_hash']
    dir_path = os.path.join(photos_path, archive_hash)

    if not os.path.exists(dir_path):
        raise HTTPNotFound(reason='Архив не существует или был удален')

    cmd = f'zip -r - {dir_path}/'
    process = await get_process(cmd)

    pid = process.pid

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = 'attachment; filename=\"photos.zip\"'
    await response.prepare(request)

    try:
        while True:
            if delay:
                await asyncio.sleep(delay)

            archive_chunk = await process.stdout.readline()

            if not archive_chunk:
                write_log(f'{cmd!r} exited with {process.returncode}')
                break

            write_log('Sending archive chunk ...')
            await response.write(archive_chunk)

    except asyncio.CancelledError:
        write_log('Download was interrupted')

        write_log(f'Killing "zip" process ...')
        cmd = "kill -9 $(pgrep -P {})".format(pid)
        await get_process(cmd)
        raise

    finally:
        response.force_close()
    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main(photos_path=None, delay=None):

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', partial(archivate, photos_path, delay)),
    ])
    web.run_app(app)


if __name__ == '__main__':
    args = parser.parse_args()

    if args.logging:
        logging.basicConfig(level=logging.INFO)
        os.environ['LOGGING_ACTIVE'] = 'True'

    photos_path = args.photos_path
    delay = args.delay

    main(photos_path, delay)
