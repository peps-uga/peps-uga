# peps-uga
Main repository to be deployed

## To add a new notebook (as a git submodule using an existing repository, ie the notebook is already in a separate github repository)
Clone this repo
    git clone https://github.io/peps-uga/peps-uga.git
then go to src/notebooks then 
    git submodule add votre-url-repo-de-notebook name_folder

If you want to have a working binder (interactive notebook) version, you need to have a front-matter.toml 
with a few infos (see notebooks/potts-example/front-matter.toml as an example).
It's better to do all your modification in your notebook repository, and commit/push.

## To add a shiny app (already hosted on a shiny server):
In src/content/shiny, copy the existing example and change the url of src.


Don't forget to commit then push :
    git commit -am "your comment"
    git push 

