---
layout: default
title: Contributing Guide
sidebar:
  nav: "contributing"
---
# Contributing Guide

<a name="overview"></a>
## Overview
Commits should follow this guide: https://chris.beams.io/posts/git-commit/

When opening a new issue, try to roughly follow the commit message format conventions above.

Be sure to include any related GitHub issue references in the commit message.  See
[GFM syntax](https://guides.github.com/features/mastering-markdown/#GitHub-flavored-markdown) for referencing issues
and commits.

Code style follows PEP8: https://www.python.org/dev/peps/pep-0008/

Please read our [Developer Certificate of Origin](https://cla.vmware.com/dco). All contributions to this repository must be signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on as an open-source patch. (Use `-s` option for `git commit` to do this automatically)

Community: https://vmwarecode.slack.com  #vcd (channel)

<a name="python"></a>
## Python
- Install Python 3.6 or greater (https://realpython.com/installing-python/)
- Install pip (Python's package manager)

Verify python and pip installation with:

```bash
> python3 --version
Python 3.7.0

> pip3 --version
pip 18.0 from /usr/local/lib/python3.7/site-packages/pip (python 3.7)
```
---

<a name="virtualenvs"></a>
## Virtual Environments
A virtual environment is a project workspace (a folder/directory) where your project's dependencies are isolated from the user/global space and from the dependencies of other projects. For example, if one project you're working on requires Flask 1.0 and another project requires Flask 2.0, these projects have different dependencies, and without virtual environments, you can't have both Flask 1.0 and 2.0. Having a virtual environment for each project will allow you to develop and test both of these projects on one machine.

The virtual environment program we will use is [`virtualenv`](https://virtualenv.pypa.io/en/stable/), though there are others that do the same thing, such as `pipenv`, `conda`, `venv`, etc. The program [`virtualenvwrapper`](https://virtualenvwrapper.readthedocs.io/en/latest/) includes a lot of helpful shortcuts/functionality for managing your virtual environments, and using it is personal preference.

When no virtual environment is active, python packages install to user or global site-packages directory.

With a virtual environment active, python packages install to the virtual environment's site-packages, and user/global site-packages are hidden from the interpreter

### Install virtualenv
```bash
> pip3 install virtualenv
```

### Virtual Environment Setup
- Create a directory to store all your virtual environments (typically the `~/.virtualenvs` folder)
- Create a virtual environment for CSE
```bash
> virtualenv ~/.virtualenvs/cse
```
- Check that the virtual environment has no packages installed using `pip freeze` or `pip list`
```bash
> pip freeze
> pip list
Package    Version
---------- -------
pip        18.1
setuptools 40.4.3
wheel      0.32.1
```
- Activate virtual environment (Linux/Mac)
```bash
> source ~/.virtualenvs/cse/bin/activate
```

- Activate virtual environment (Windows)
```bash
> source ~/.virtualenvs/cse/Scripts/activate
```

- Deactivate virtual environment
```bash
> deactivate
```

More on virtual environments:
- https://www.geeksforgeeks.org/python-virtual-environment/
- https://realpython.com/python-virtual-environments-a-primer/

---

<a name="projectsetup"></a>
## Project Setup

### Git Setup
- VMware CSE repository (https://github.com/vmware/container-service-extension) is the **upstream** remote repository
- Fork VMware CSE repository to your personal Github account
- Your forked CSE repository (https://github.com/USERNAME/container-service-extension) is the **origin** remote repository

```bash
# Clone your forked repository to your local machine
> git clone https://github.com/USERNAME/container-service-extension

# Register the upstream remote repository as one of your project's known remote repositories
> git remote add upstream https://github.com/vmware/container-service-extension
origin	https://github.com/USERNAME/container-service-extension.git (fetch)
origin	https://github.com/USERNAME/container-service-extension.git (push)
upstream	https://github.com/vmware/container-service-extension.git (fetch)
upstream	https://github.com/vmware/container-service-extension.git (push)
```
---

### Creating a Development Environment
- Activate virtual environment (Always be in virtual environment when developing/testing)
- Install CSE package to virtual environment so we can test our code changes
```bash
# -e for editable mode. Code changes are reflected without installing again
> pip install -e path/to/container-service-extension
> pip list
Package                     Version      Location
--------------------------- ------------ ----------------------------------------------
cachetools                  2.1.0
certifi                     2018.8.24
chardet                     3.0.4
Click                       7.0
colorama                    0.3.9
container-service-extension 1.1.1.dev13  /Users/USERNAME/container-service-extension
entrypoints                 0.2.3
flufl.enum                  4.1.1
humanfriendly               4.16.1
idna                        2.7
keyring                     12.0.0
lxml                        4.2.5
pika                        0.12.0
pip                         18.1
pycryptodome                3.4.11
Pygments                    2.2.0
pyvcloud                    20.0.0
pyvmomi                     6.7.0.2018.9
PyYAML                      3.13
requests                    2.19.1
setuptools                  40.4.3
six                         1.11.0
tabulate                    0.8.2
urllib3                     1.23
vcd-cli                     21.0.0
vsphere-guest-run           0.0.6
wheel                       0.32.1
```

<a name="usage"></a>
## CSE Usage and Testing

### Configure vcd-cli to enable `vcd cse ...` commands
Edit `~/.vcd-cli/profiles.yaml` to include this section:
```
extensions:
- container_service_extension.client.cse
```
If `~/.vcd-cli/profiles.yaml` doesn't exist, logging in to vCD via **vcd-cli** will create it
```bash
> vcd login IP ORGNAME USERNAME -iwp PASSWORD
```
---
### Useful Commands
```bash
# see all commands with:
> vcd -h
> vcd cse -h
> cse -h

### Most 'vcd cse ...' commands require you to be logged in to vCD
# login as system administrator
> vcd login ip system USERNAME -iwp PASSWORD

# login as org user
> vcd login ip ORGNAME USERNAME -iwp PASSWORD

# use a target org while logged in as system administrator
> vcd org use ORGNAME

# see current login info
> vcd pwd
```
---
### Set up vCD for Testing
*In a vCD instance where you are system administrator. Assume default settings unless stated otherwise*
- Create External Network with internet connection
    - May need static IP pool
- Create org
- Create org VDC for org
- Add org VDC network to org VDC. Org network must have internet access
  - vcd > org > Administration > Cloud Resources > Virtual Datacenters > orgvdc > Org VDC Networks

---

### Set up config.yaml
```bash
# get a sample config file to edit
cse sample > config.yaml
```

- Configure **amqp** settings
  - vcd > System > Administration > System Settings > Extensibility > Settings > AMQP Broker Settings
- Configure **vcd** settings
  - Set **api_version**
  - Set **host**, **password**, **username**
- Configure **vcs** settings
  - Set **name** using name from vcd > System > Manage & Monitor > vSphere Resources > vCenters
  - Set **username** and **password**
- Configure broker settings
  - Set **catalog** to public shared catalog within org where the template will be published to (usually cse)
  - Set **network** to org VDC network that will be used during the install process. Should have outbound access to the public internet
  - Set **org** to the vCD org that will store the kubernetes templates
  - Set **vdc** to VDC for the org that will be used during the install process
- Adjust config file permissions with: `chmod 600 path/to/config.yaml` (unsure how to do this step on windows)

---

### Testing Cheat Sheet
- Current working directory should have the script files or the `container-service-extension/scripts/` directory (fix is in review for this)
- CSE Server log is **cse.log**
- CSE Installation log is **cse-check.log**
- **vcd-cli** logs is **vcd.log**

```bash
> cse install -c config.yaml
> cse version
> cse check -c config.yaml
> cse run -c config.yaml
> vcd login IP ORGNAME USERNAME -iwp PASSWORD
> vcd cse version
> vcd cse template list
> vcd cse system info
> vcd cse cluster create mycluster -n NETWORKNAME
> vcd cse cluster info mycluster
> vcd cse node create mycluster -n NETWORKNAME
> vcd cse node list mycluster
> vcd cse node info mycluster nodename
> vcd cse node delete mycluster nodename
> vcd cse cluster delete mycluster
```
---
<a name="git"></a>
## Standard Git Workflow
- Never push to **upstream master**
- Check if upstream master has any updates
    - if it does, pull these changes into your local project's master branch, then push these changes to update your remote origin master branch
```bash
> git fetch upstream
> git pull upstream master --rebase # (IF CHANGES EXIST)
> git push origin master # (IF CHANGES EXIST)
```
- Make new branches from your local master when developing
```bash
> git checkout -b mybranch
```
- Make changes, stage, commit, etc.
- Push this local branch to remote origin
```bash
> git push origin mybranch
```
- Open a pull request from **origin mybranch** to **upstream master** :D

Common Git commands:
```bash
### Harmless commands
# see current branch and state of changes
> git status

# see all local branches
> git branch

# see remote upstream's changes, but don't apply
> git fetch upstream

# switch local branches
> git checkout branchname

# view git commit log
> git log

### Commands with side effects
# signs the commit message to avoid annoying github bot
> git commit -s

# Adds changes to last commit and change commit message
> git commit --amend

# places all uncommitted changes into stash
> git stash

# lists all stashed changes
> git stash list

# applies the most recent stash and removes it from stash
> git stash pop

# without --rebase, applies pulled code on top of your current changes. With --rebase, applies the remote changes first, then applies your code changes on top of those.
> git pull --rebase

# allow user to modify commit history for latest 5 commits (squashing is very useful)
> git rebase -i HEAD~5

# Forces the remote origin branch to be the same as your local branch. Can be used to update an open pull request after using git rebase locally. Fairly safe to use since nothing should be forked from your remote origin
> git push origin branchname --force
```

Git resources:
- https://services.github.com/on-demand/downloads/github-git-cheat-sheet/
- https://guides.github.com/activities/forking/
- https://www.atlassian.com/git/tutorials/saving-changes/gitignore#personal-git-ignore-rules
- http://shafiulazam.com/gitbook/4_rebasing.html
