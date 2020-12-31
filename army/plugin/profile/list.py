from army.api.log import log
from army.api.debugtools import print_stack
from army.api.repository import load_repositories
from army.api.click import verbose_option 
from army.api.profile import load_profile_list
from army.plugin.profile.profile_group import profile
import click
import sys

from army import prefix

@profile.command(name='list', help='List available profiles')
@verbose_option()
@click.pass_context
def profile_list(ctx, **kwargs):
    log.info(f"profile list")

    profiles = load_profile_list()
    
    if len(profiles)==0:
        print("no profile found", file=sys.stderr)
        return

    column_name = ['name']
    column_description = ['description']
    column_path = ['path']
#
    for profile in profiles:
        column_name.append(profile.name)
        column_description.append(str(profile.version))
        column_path.append(profile.description)
  
    max_name = len(max(column_name, key=len))
    max_description = len(max(column_description, key=len))
    max_path = len(max(column_path, key=len))
  
    for i in range(len(column_name)):
        print(f"{column_name[i].ljust(max_name)} | ", end='')
        print(f"{column_description[i].ljust(max_description)} | ", end='')
        print(f"{column_path[i].ljust(max_path)} | ", end='')
        print()
