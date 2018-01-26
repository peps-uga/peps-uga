import re
import json
import toml
import sys
import shlex
import subprocess as sp
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import *

import nbformat

from nbconvert import HTMLExporter
from nbconvert.preprocessors import Preprocessor

from traitlets.config import Config


from fabric.api import *


@task
def render_notebooks():
    """
    Render jupyter notebooks in notebooks directory to html in static/full_html directory.
    """
    notebooks = Path('notebooks').glob('**/*.ipynb')
    for notebook in notebooks:
        if (not str(notebook).startswith('.')) and ('untitled' not in str(notebook).lower()):
            update_notebook_metadata(notebook)
            write_hugo_formatted_nb_to_html(notebook)


@task
def publish():
    """
    Publish notebook to github pages.

    Assumes this is yourusername.github.io repo aka
    User Pages site as described in
    https://help.github.com/articles/user-organization-and-project-pages/
    and that you're using the master branch only
    to have the rendered content of your blog.
    """
    with settings(warn_only=True):
        if local('git diff-index --quiet HEAD --').failed:
            local('git status')
            abort('The working directory is dirty. Please commit any pending changes.')

    # deleting old publication
    local('rm -rf public')
    local('mkdir public')
    local('git worktree prune')
    local('rm -rf .git/worktrees/public/')

    # checkout out gh-pages branch into public
    local('git worktree add -B master public upstream/master')

    # removing any existing files
    local('rm -rf public/*')

    # generating site
    render_notebooks()
    local('hugo')

    # commit
    with lcd('public'), settings(warn_only=True):
        local('git add .')
        local('git commit -m "Committing to master (Fabfile)"')

    # push to master
    local('git push upstream master')
    print('push succeeded')


def notebook_to_html(path: Union[Path, str]) -> str:
    """
    Convert jupyter notebook to html

    Args:
        path: path to notebook

    Returns: full html page

    """
    with open(Path(path)) as fp:
        notebook = nbformat.read(fp, as_version=4)
        assert 'front-matter' in notebook['metadata'], "You must have a front-matter field in the notebook's metadata"
        front_matter_dict = dict(notebook['metadata']['front-matter'])

    html_exporter = HTMLExporter()

    html, _ = html_exporter.from_notebook_node(notebook)

    with open(Path(path.parents[0],"front-matter.toml")) as fm:
        front_matter_overload = toml.load(fm)

    for key in front_matter_overload.keys():
        front_matter_dict[key] = front_matter_overload[key]
    front_matter = json.dumps(front_matter_dict, indent=2)


    return html,front_matter


def write_hugo_formatted_nb_to_html(notebook: Union[Path, str], render_to: Optional[Union[Path, str]] = None, store_to: Optional[Union[Path, str]] = None) -> Path:
    """
    Convert Jupyter notebook to html and write it to the appropriate file.

    Args:
        notebook: The path to the notebook to be rendered
        render_to: The directory we want to render the notebook to
    """
    notebook = Path(notebook)
    notebook_metadata = json.loads(notebook.read_text())['metadata']
    rendered_html_string, front_matter  = notebook_to_html(notebook)
    slug = notebook_metadata['front-matter']['slug']
    render_to = render_to or notebook_metadata['hugo-jupyter']['render-to'] or 'content/notebooks/'
    store_to = store_to or notebook_metadata['hugo-jupyter']['store-to'] or '/full_html/'

    if not render_to.endswith('/'):
        render_to += '/'

    rendered_html_file = Path('static'+store_to, slug + '.html') # we need to go into static folder to avoid indexation of the file

    if not rendered_html_file.parent.exists():
        rendered_html_file.parent.mkdir(parents=True)

    rendered_html_file.write_text(rendered_html_string)
    print(notebook.name, '->', rendered_html_file.name)

    # create md file with iframe to notebook inside :
    # added <!--more--> comment to prevent summary creation
    if 'repo' in json.loads(front_matter).keys():
        repo = json.loads(front_matter)['repo']
        repo=repo.replace("https://github.com", "gh")
        repo=repo.replace("https://gitlab.com", "gl")
        base_binder_url = "https://mybinder.org/v2/%s/master?filepath=%s"%(repo,notebook.name)
        dynlink = 'Click to access <a href="%s" target="_blank">interactive version</a> \n'%(base_binder_url)
    else:
        dynlink=""
    md = dynlink + '{{< iframe src = "%s">}}'%Path(store_to, slug + '.html')
    rendered_md_string = '\n'.join(('---', front_matter, '---', '<!--more-->', md))
    rendered_md_file = Path(render_to, slug + '.md')
    if not rendered_md_file.parent.exists():
        rendered_md_file.parent.mkdir(parents=True)

    rendered_md_file.write_text(rendered_md_string)


    return rendered_html_file,rendered_md_file


def update_notebook_metadata(notebook: Union[Path, str],
                             title: Union[None, str] = None,
                             subtitle: Union[None, str] = None,
                             date: Union[None, str] = None,
                             slug: Union[None, str] = None,
                             categories: list = None,
                             render_to: str = None,
			     store_to: str = None,
						):
    """
    Update the notebook's metadata for hugo rendering

    Args:
        notebook: notebook to have edited
    """
    notebook_path: Path = Path(notebook)
    notebook_data: dict = json.loads(notebook_path.read_text())
    old_front_matter: dict = notebook_data.get('metadata', {}).get('front-matter', {})

    # generate front-matter fields
    title = title or old_front_matter.get('title') or notebook_path.stem
    subtitle = subtitle or old_front_matter.get('subtitle') or 'Generic subtitle'
    date = date or old_front_matter.get('date') or datetime.now().strftime('%Y-%m-%d')
    slug = slug or old_front_matter.get('slug') or title.lower().replace(' ', '-')
    categories = categories or old_front_matter.get('categories') or ["Notebook"]

    front_matter = {
        'title': title,
        'subtitle': subtitle,
        'date': date,
        'slug': slug,
        'categories': categories,
    }

    # update front-matter
    notebook_data['metadata']['front-matter'] = front_matter

    # update hugo-jupyter settings
    render_to = render_to or notebook_data['metadata'].get('hugo-jupyter', {}).get('render-to') or 'content/notebooks/'
    store_to = store_to or notebook_data['metadata'].get('hugo-jupyter', {}).get('store-to') or '/full_html/'

    hugo_jupyter = {
        'render-to': render_to,
        'store-to': store_to
    }
    notebook_data['metadata']['hugo-jupyter'] = hugo_jupyter

    # write over old notebook with new front-matter
    notebook_path.write_text(json.dumps(notebook_data))

    # make the notebook trusted again, now that we've changed it
    sp.run(['jupyter', 'trust', str(notebook_path)])

