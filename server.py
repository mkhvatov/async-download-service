import asyncio
import os
import logging
import argparse
from functools import partial

from envparse import env
from aiohttp import web
from aiohttp.web import HTTPNotFound
import aiofiles


DEFAULT_PHOTOS_PATH = env.str('DEFAULT_PHOTOS_PATH', default='test_photos')
DEFAULT_DELAY = env.int('DEFAULT_DELAY', default=0)
DEFAULT_CHUNK_SIZE = env.int('DEFAULT_CHUNK_SIZE', default=102400)


parser = argparse.ArgumentParser(description='Script runs server for downloading photo archives')
parser.add_argument('--logging',
                    action='store_true',
                    default=None,
                    help='activate logging',
                    )
parser.add_argument('--photos_path',
                    type=str,
                    default=DEFAULT_PHOTOS_PATH,
                    help='custom path (str) for main photo directory; default=\'./test_photos\'',
                    )
parser.add_argument('--delay',
                    type=int,
                    default=DEFAULT_DELAY,
                    help='custom delay (seconds, int) for download response; default=0',
                    )


async def archivate(photos_path, delay, request):

    archive_hash = request.match_info['archive_hash']
    working_directory = os.path.join(photos_path, archive_hash)
    if not os.path.exists(working_directory):
        raise HTTPNotFound(reason='Архив не существует или был удален')

    cmd = ['zip', '-r', '-', '.']
    process = await asyncio.create_subprocess_exec(
        *cmd, cwd=working_directory,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = 'attachment; filename=\"photos.zip\"'
    await response.prepare(request)

    try:
        while True:
            await asyncio.sleep(delay)

            archive_chunk = await process.stdout.read(DEFAULT_CHUNK_SIZE)

            if not archive_chunk:
                logging.info(f'{cmd!r} exited with {process.returncode}')
                break

            logging.info('Sending archive chunk ...')
            await response.write(archive_chunk)

    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info('Download was interrupted')
        logging.info(f'Killing "zip" process ...')

    except BaseException as error:
        logging.info(f'Unexpected error: {error}')

        raise

    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()

        response.force_close()
    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main():
    args = parser.parse_args()

    if args.logging:
        logging.basicConfig(level=logging.INFO)

    photos_path = args.photos_path
    delay = args.delay

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', partial(archivate, photos_path, delay)),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
