# Blendgit
Keep track of revisions of blend files in git from blender.  
This addon is forked version of [**scorpion81/Blender-Destructability-Editor/blendgit**](https://github.com/scorpion81/Blender-Destructability-Editor/tree/master/blendgit)

## Installation
1. Download zip file from [latest release]()
2. Launch Blender and open Preferences
3. In Add-ons section, click "Install..." button and select "blendgit.zip"

## Features
### Easy & Quick UI
Simple command operations from UI.  
Access quickly from any workspaces.

### Flexible Operations
Use commands directly and interactively.  
Register commands as shortcuts and excute it quickly.

### Visual Log
Register log commands and switch list visual by purpose.  
Set thumbnail of commit to check progress with image.

## About Merge
Since .blend file is binary, **conflicts are inevitable**.  
Therefore I impremented some **salvaging-data** funcitons.  

### Archive Commit
Using `$git archive ...`, get zip of tracked files from old commit.

### Pick Library
Pick librarary data from old .blend file tracked at old commit.

### Checkout File
Using `$git checkout ...`, get tracked files from old commit.
