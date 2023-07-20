import os
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from portfolio42_api.models import Project, Skill, User, Cursus
from portfolio42_api.management.api42 import Api42, ApiException
import logging

def parser_add_db_command(cmd):
    cmd.add_argument('intra_ids',
                nargs='*',
                action='store',
                help='Which intra id(s) to update',
                metavar='intra id',
                type=int)

def update_db(api: Api42, endpoint : str, func : callable, ids : [] = []):

    # Api settings
    per_page = 100
    page = 0 # This will increase in the while loop
    projects_returned = per_page

    params = {'per_page': per_page, 'page': page}
    if (len(ids) > 0):
        if (len(ids) > 100):
            raise ValueError()
        params['filter[id]'] = ','.join(map(str, ids))


    while (projects_returned == per_page):
        json = {}

        try:
            json = api.get(endpoint, params)
            logging.info(f"Obtained ({len(json)}) objects from api request")
        except ApiException as e:
            logging.error(f"Error on 42 API request")
            break

        for obj in json:
            func(obj)
        
        page += 1
        params['page'] = page
        projects_returned = len(json)

        # If we are looking for specific ids we do not need to make another request
        if (len(ids) > 0):
            break

def update_project(project):
    p, created = Project.objects.get_or_create(intra_id=project['id'])
    
    p.name = project['name'][:50]
    if (created):
        
        try:
            p.description = project['description']
        except:
            p.description = project['slug']

    p.exam = project['exam']
    p.solo = False # todo: REMOVE THIS
    p.save()

    if (created):
        logging.info(f"Created new project: {p.name} (id: {p.id}, intra_id: {p.intra_id})")
    else:
        logging.info(f"Refreshed project: {p.name} (id: {p.id}, intra_id: {p.intra_id})")
    logging.debug(f"Updated project ({p.id}) with: intra_id={p.intra_id}, desc={p.description}, exam={p.exam}")

def update_skill(skill):
    s, created = Skill.objects.get_or_create(intra_id=skill['id'])
    
    s.name = skill['name'][:100]
    s.save()

    if (created):
        logging.info(f"Created new skill: {s.name} (id: {s.id}, intra_id: {s.intra_id})")
    else:
        logging.info(f"Refreshed skill: {s.name} (id: {s.id}, intra_id: {s.intra_id})")
    logging.debug(f"Updated skill ({s.id}) with: intra_id={s.intra_id}, name={s.name}")

def update_cursus(cursus):
    c, created = Cursus.objects.get_or_create(intra_id=cursus['id'])
    
    c.name = cursus['name'][:50]
    c.kind = cursus['kind'][:50]
    c.save()

    if (created):
        logging.info(f"Created new cursus: {c.name} (id: {c.id}, intra_id: {c.intra_id})")
    else:
        logging.info(f"Refreshed cursus: {c.name} (id: {c.id}, intra_id: {c.intra_id})")
    logging.debug(f"Updated cursus ({c.id}) with: intra_id={c.intra_id}, name={c.name}, kind={c.kind}")

def update_users(api : Api42, ids : [] = []):
    per_req = 100 # Amount of users to request
    users = User.objects.all()
    if (len(ids) > 0):
        users = User.objects.filter(intra_id__in=ids)

    i = 0
    total = users.count()
    while (i < total):
        end_i = min(i + per_req, total)
        user_batch = users[i:end_i]
        params = { 'filter[id]': (','.join(map(lambda u : str(u.intra_id), user_batch)))}
        r = api.get('/v2/users', params)

        logging.info(f"Obtained ({len(r)}) users from api request")

        for u_json in r:
            intra_id = u_json['id']
            u = User.objects.get(intra_id=intra_id)

            u.intra_username = u_json['login']
            u.first_name = u_json['first_name']
            u.last_name = u_json['last_name']
            u.email = u_json['email']
            u.intra_url = u_json['url']
            u.image_url = u_json['image']['link']

            u.save()

            logging.info(f"Refreshed user: {u.intra_username} (id: {u.id}, intra_id: {u.intra_id})")

        i += per_req

class Command(BaseCommand):
    help = "Sync the database with the intra api"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='command', required=True, metavar='sub-command')

        parser_add_db_command(subparsers.add_parser('user', help="Update user table"))
        parser_add_db_command(subparsers.add_parser('cursus', help="Update cursus table"))
        parser_add_db_command(subparsers.add_parser('project', help="Update project table"))
        parser_add_db_command(subparsers.add_parser('skill', help="Update skill table"))

        parser_add_db_command(subparsers.add_parser('relations', help="Update relations in the database"))

        cmd_clear_cache = subparsers.add_parser('clear_cache')
        cmd_clear_cache.add_argument('--cache-dir',
                                     action='store',
                                     dest='cache_dir',
                                     help='Folder of where the cache is stored',
                                     default=Path("./cache"),
                                     type=Path)


        parser.add_argument('--no-logfile',
                            action='store_true',
                            dest="no_logfile",
                            help='If it should not create a logfile',
                            default=False)
        parser.add_argument('--log-dir',
                            action='store',
                            dest='log_dir',
                            help='Where to store the logs',
                            default=Path("./logs"),
                            type=Path)

    def handle(self, *args, **options):
        command = options['command']

        # setup logging
        log_level = options['verbosity'] * 10
        log_format = "[%(asctime)s][%(levelname)s] %(message)s"
        log_time_format = "%y%m%d%H%M%S"
        log_handlers = []
        if (log_level > 0):
            if (not options['no_logfile']):
                log_dir : Path = options['log_dir']
                log_dir.mkdir(parents=True, exist_ok=True)
                logfile_name = f"{datetime.now().strftime('%y%m%d%H%M%S')}_{command}.log"
                handler = logging.FileHandler(f"{log_dir.absolute()}/{logfile_name}")
                log_handlers.append(handler)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter(log_format))
        log_handlers.append(sh)


        logging.basicConfig(level=log_level,
                            format=log_format,
                            datefmt=log_time_format,
                            handlers=log_handlers)

        api = Api42(os.environ.get('INTRA_UID'), os.environ.get('INTRA_SECRET'))

        match command:
            case 'project':
                update_db(api, '/v2/projects', update_project, options['intra_ids'])
            case 'skill':
                update_db(api, '/v2/skills', update_skill, options['intra_ids'])
            case 'cursus':
                update_db(api, '/v2/cursus', update_cursus, options['intra_ids'])
            case 'user':
                update_users(api, options['intra_ids'])

