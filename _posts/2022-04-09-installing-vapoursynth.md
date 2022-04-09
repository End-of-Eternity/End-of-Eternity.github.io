---
layout: post
title: "Installing Vapoursynth"
category: "Vapoursynth Scripting"
date: 2022-04-09 13:19:00 +0100
---

It's been 2 years and one day since my first post here and I've done far less than I intended. This
is mainly due to my inability to write something that I am happy with, and so most posts get
deleted. Still, I am interested in writing about things, and people still ask me the same questions
over and over, so it would make sense to write a blog post to link those people to. Like this
question, for example.

## How do I setup Vapoursynth?

I could just do the braindead answer and link to [the docs](http://www.vapoursynth.com/doc/installation.html),
which would make some sense, after all, these are the official installation instructions,
but they aren't particularly helpful past getting Vapoursynth on your machine, and the [applications list](http://www.vapoursynth.com/doc/applications.html)
is well out of date at this point (vsedit is now completely broken - F). So, in this post, I'll
cover how I would set up a new machine for Vapoursynth script development.

I assume at least a basic understanding of the command line for most of this tutorial, but for those
who are new to this, if I say "run `x`," I generally mean on the command line. This can be accessed
by Powershell (recommended) or cmd on windows. To open Powershell, use Win+X, and select "Windows
PowerShell." For further reading, the [mozilla](https://developer.mozilla.org/en-US/docs/Learn/Tools_and_testing/Understanding_client-side_tools/Command_line)
docs are pretty good.

### Prerequisites

- **Windows 10/11**

  It's not like Vapoursynth doesn't run on linux distros or MacOS, I just don't have a Mac, and
  there are too many linux distros to cover. Many of the most popular ones have Vapoursynth on their
  respective package managers. If you are really struggling, contact me and I can probably help.

- **[Python 3.9](https://www.python.org/downloads/)**

  I hate python. I can never seem to get it to play nicely with anything. Probably a me thing. My
  suggestion for installation is to run the installer (as admin), customise installation and select
  "for all users." Vapoursynth can be installed for just the user, but it's caused me problems in
  the past, and I know that this just works™. Also make sure to select pip so you don't have to grab
  it later.

  I would suggest making sure all old Python installations are gone before installing 3.9. You can
  have multiple python installs, and it can work, but I can't ever get it to, so you'll be on your
  own.

  As of today, the latest release of Vapoursynth (R57)
  supports 3.9. You can compile it yourself for 3.10, but that's outside of the scope of this post.
  I will update the post when this changes.

- **[Visual Studio Code](https://code.visualstudio.com/)**

  Any code editor with a built in terminal will work (for example, Atom), however I use vscode
  myself, so will be using that for this guide.

  Make sure to install the [Python Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python)!

- **[pip](https://pip.pypa.io/en/stable/installation/)**

  Not strictly necessary, however many packages are hosted on pypi, and pip just makes installation
  of them easier. If you forgot to install it with Python earlier, run `python -m ensurepip`.

- **[git](https://git-scm.com/download/win)**

  Also not necessary, but makes installation of packages not on pypi (like EoEfunc) easier to get.

### Vapoursynth

Vapoursynth R57 can be downloaded from [here](https://github.com/vapoursynth/vapoursynth/releases/download/R57/VapourSynth64-R57.exe)
Run the installer as administrator, and just leave everything selected. Afterwards, go to the
console and run `python -c 'from vapoursynth import core; print(core.version())'`. You should get
details of your Vapoursynth installation printed to the console. If not, something's gone wrong.

### Plugins / Scripts

Vapoursynth can be used as is, vspipe should now be in your PATH (i.e. you can run `vspipe`), so you
can run a basic script, however you've got no extra plugins or packages, nor any way to preview
your outputs. You can browse [VSDB](https://vsdb.top/) for many plugins/packages that you might want,
but if you just want a quick way to download basically all the stuff you'll ever need, feel free to
use the [Judas Vapoursynth Install Script](/assets/vapoursynth-installation/Vapoursynth%20Install.7z).
To run, just extract it, and then right click on `install.ps1` and click "Run with PowerShell."
Assuming you installed Python/Vapoursynth as described above, you should be able to leave the
installation paths as they are (hit enter twice).

Note that this is an internal Judas install script, so some of the stuff in here is held at an older
version than is available for compatibility reasons (e.g. lvsfunc, vardefunc). These can be upgraded
manually via `pip` should you wish to. It also assumes you have all the prerequisites above (except
vscode) installed already.

### Previewing

Next, I'd suggest installing some way of previewing your scriots. My favourite previewer is Endill's
[Vapoursynth Preview](https://github.com/Endilll/vapoursynth-preview). He hasn't yet upgraded it to
work with the latest Vapoursynth version, so I'd suggest using [Akarin's fork](https://github.com/AkarinVS/vapoursynth-preview).
To install, open the folder you want vspreview to be in (I use C:\\PATH, but anywhere works), hold
shift and right click in the folder, and click on "Open PowerShell window here."  Now run
`git clone https://github.com/AkarinVS/vapoursynth-preview.git`. This will copy all the files from
the git repository into a new folder called "vapoursynth-preview."

Now, we need to add vspreview as a launch configuration in vscode. Open vscode, and press F1, then
type "Preferences" into the search bar. Click on "Preferences: Open Settings (JSON)". Paste the
following into the file that opens, replacing the "program" path with wherever you installed
vspreivew. Make sure to use double backslashes in the path so it doesnt break!

```json
{
    "files.associations": {
        "*.vpy": "python",
    },
    "launch": {
        "configurations": [
            {
                "args": [
                    "${file}"
                ],
                "console": "integratedTerminal",
                "name": "Vapoursynth: Preview",
                "program": "C:\\Path\\To\\vapoursynth-preview\\run.py",
                "request": "launch",
                "type": "python"
            },
        ],
        "version": "0.2.0"
    },
}
```

Now you should be able to press F5 to preview whatever script you currently have open. Any easy test
for this is below, save it as `test.vpy` and try pressing F5. You should get a window open with a
red frame. I've also included a file association for vpy to python so that you get syntax
highlighting.

My full vscode settings are available [here](/assets/vapoursynth-installation/settings.json), though
I warn you, it's not organised and half the settings in there are old. If you do use them, you
should also install [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance),
[black](https://black.readthedocs.io/en/stable/) (`pip install black`) and [flake8](https://flake8.pycqa.org/en/latest/)
(`pip install flake8`), as well as [Fira Code](https://github.com/tonsky/FiraCode/wiki/Installing#windows).

```python
import vapoursynth as vs
core = vs.core

core.std.BlankClip(color=[255, 0, 0]).set_output()
```

### All done!

Hopefully this has been helpful for anyone trying to setup an environment to start learning
Vapoursynth. Eventually I'll write a proper post on learning to write scripts without it being too
hand holdy like [my initial attempt](/old/2020-04-08-vapoursynth-getting-started). If you run into
any issues, my dm's are always open (End of Eternity#6292).

Cheers, EoE