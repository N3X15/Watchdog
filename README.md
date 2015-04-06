# Watchdog
A modular game daemon watchdog script, written in Python.

Automatically downloads, installs, updates, and configures Garry's mod, and can probably be tweaked to handle other Source-based games, too.

Modular, so other game engines can easily be added.

## License

MIT License

## Installing

First, you need to download Watchdog and install its dependencies.  If you don't have Python 2.7 installed, go get it.

```bash 
git clone https://github.com/N3X15/Watchdog watchdog
pip install pyyaml Jinja2 psutil pyparsing twisted
git submodule update --init --recursive
```

1. Now, find the configuration template you'd like to use within conf.templates, and save it as ```watchdog.yml```, in the same directory as ```Watchdog.py```.
2. Edit it as desired.
3. Start Watchdog.py: ```python Watchdog.py```
4. Sit back and enjoy a nice cup of coffee as your server is installed for you.

## Updating

Simple:

```bash
git pull
git submodule update
```

If you're missing anything, Watchdog will tell you what to do.