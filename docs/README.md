# Container Service Extension (CSE) Documentation 

Welcome to the CSE documentation directory. This README.md has instructions 
for setting up and modifying documentation. 

## Enabling Documentation in Github

CSE uses Github Pages to publish documentation. Follow the steps shown 
below to enable documentation in the master repo or a fork. 

1. Go to `Settings` on your Github Project. It's a button at the top of the 
main project page.  (If you do not see the button you may need to get 
admin access enabled on your account.)
2. Scroll down to the Github Pages section. Select master/docs as the source
for Github Pages. 
3. Save your changes. 

It may take a few minutes for the change to propagate.  When it is complete
you will see a notice like `Your site is published at https://<name>.github.io/container-service-extension/`.  Point your browser to that URL to see 
the generated documentation. 

## How CSE Documentation Works

Github Pages renders .md files using Jekyll.  You can read more about 
Jekyll at [jekyllrb.com](https://jekyllrb.com/docs/).  The documentation
sources must be in the master branch and directory selected in Settings. 

CSE documentation has a header, left-hand navigation, right-side content, 
and a footer.  The files that make this happen are organized as follows. 

* The Jekyll site configuration is in _config.yml
* The template used to lay out page html is in _layout/default.html
* The navigation menu is in _data/navigation.yml
* The code that generates the navigation links is in _includes/navigation.hml.
* The content is in files labeled in all-caps starting with INTRO.md. 

The HTML layout assumes HTML5.  It will not display correctly on older
browsers. 

## How to Make Changes

Just edit the files and check them in!

Before you do that it's a good idea to run them using a local version of 
Jekyll. See [Setting up your GitHub Pages site locally with Jekyll](https://help.github.com/articles/setting-up-your-github-pages-site-locally-with-jekyll/) 
for a helpful guide to this. 

Content changes do not require any special knowledge of HTML: 

1. Add new files e.g. FOO.md or edit existing ones. 
2. Edit _data/navigation.yml to add nav links to new pages and sections.
3. If you make content changes that affect navigatation test them fully to avoid broken links. 

If you need to change the page layout it's a good idea to learn about how 
Jekyll works first. (Start with [this tutorial](https://jekyllrb.com/docs/step-by-step/01-setup/).) 

You'll also need to understand CSS since we use it to control
alignment in the browser.
