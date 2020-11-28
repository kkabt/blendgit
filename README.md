# Blendgit
Keep track of revisions of blend files in git from blender.  
This addon is forked version of [**scorpion81/Blender-Destructability-Editor/blendgit**](https://github.com/scorpion81/Blender-Destructability-Editor/tree/master/blendgit)


## Installation
1. Download zip file from [latest release](../../releases/latest)
2. Launch Blender and open Preferences
3. In Add-ons section, click "Install..." button and select "blendgit.zip"


## Features
### Easy & Quick UI
Simple command operations from UI.  
![file](https://user-images.githubusercontent.com/45528649/100524655-55266a80-31fd-11eb-92c8-9f0808ac86d5.gif)

Access quickly from any workspaces.  
![topbar](https://user-images.githubusercontent.com/45528649/100524668-67a0a400-31fd-11eb-8e7e-148b1f9a3d26.gif)

### Flexible Operations
Use commands directly and interactively.  
Register commands as shortcuts and excute it quickly.  
![shortcut](https://user-images.githubusercontent.com/45528649/100524676-6ff8df00-31fd-11eb-9955-43f9e84bb18a.gif)

### Visual Log
Register log commands and switch list visual by purpose.  
Set thumbnail of commit to check progress with image.  
![log](https://user-images.githubusercontent.com/45528649/100524679-771fed00-31fd-11eb-9da7-3cc678525729.gif)

## About Merge
Since .blend file is binary, **conflicts are inevitable**.  
Therefore I impremented some **salvaging-data** funcitons.  

### Archive Commit
Using `$git archive ...`, get zip of tracked files from old commit.

### Pick Library
Pick librarary data from old .blend file tracked at old commit.

### Checkout File
Using `$git checkout ...`, get tracked files from old commit.
