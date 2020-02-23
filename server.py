import asyncio
import os
import logging
import argparse

from aiohttp import web
from aiohttp.web import HTTPNotFound
import aiofiles


DEFAULT_PHOTOS_DIR = './test_photos'
DEFAULT_DELAY = 0


parser = argparse.ArgumentParser(description='Script runs server for downloading photo archives')
parser.add_argument('--logging',
                    action='store_true',
                    default=None,
                    help='activate logging',
                    )
parser.add_argument('--photos_dir',
                    type=str,
                    default=None,
                    help='custom path (str) for main photo directory; default=\'./test_photos\'',
                    )
parser.add_argument('--delay',
                    type=int,
                    default=None,
                    help='custom delay (seconds, int) for download response; default=0',
                    )


def set_envvar(envvar, value):
    os.environ[envvar] = value


def write_log(message):
    if os.getenv('LOGGING_ACTIVE'):
        logging.info(message)


async def get_process(cmd):
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    return process


async def archivate(request, photos_dir, delay):
    if not photos_dir:
        photos_dir = DEFAULT_PHOTOS_DIR
    if not delay:
        delay = DEFAULT_DELAY

    archive_dir = request.match_info['archive_hash']
    dir_path = os.path.join(photos_dir, archive_dir)

    if not os.path.exists(dir_path):
        raise HTTPNotFound(reason='Архив не существует или был удален')

    cmd = "cd {} && zip -r - {}/".format(photos_dir, archive_dir)
    process = await get_process(cmd)

    pid = process.pid

    response = web.StreamResponse()
    response.headers['Content-Disposition'] = 'attachment; filename=\"photos.zip\"'
    await response.prepare(request)

    try:
        while True:
            await asyncio.sleep(delay)
            write_log('Sending archive chunk ...')

            archive_chunk = await process.stdout.readline()
            if not archive_chunk:
                return response

            await response.write(archive_chunk)
            await asyncio.sleep(0)

    finally:
        if process.returncode is None:
            write_log('Download was interrupted')

            cmd = "kill -9 $(pgrep -P {})".format(pid)
            close_process = await get_process(cmd)


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main(photos_dir=None, delay=None):

    def make_archieve(request):
        return archivate(request, photos_dir, delay)

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', make_archieve),
    ])
    web.run_app(app)


if __name__ == '__main__':
    args = parser.parse_args()

    if args.logging:
        logging.basicConfig(level=logging.INFO)
        set_envvar('LOGGING_ACTIVE', 'True')

    photos_dir = args.photos_dir
    delay = args.delay

    main(photos_dir, delay)
