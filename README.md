# Description
Telegram bot using [EdgeGPT](https://github.com/acheong08/EdgeGPT)
unofficial API

**Content**:
- [Description](#description)
- [Requirements](#requirements)
- [Bot commands](#bot-commands)
- [Run](#run)
- [Docker](#docker)
  - [Manual build](#manual-build)
  - [Dockerhub image](#dockerhub-image)
- [Contributing](#contributing)
  - [Pre-commit hooks](#pre-commit-hooks)
  - [VSCode project settings](#vscode-project-settings)
  - [Contributors](#contributors)
- [License](#license)

# Requirements
- python
- git

# Bot commands
Commands available to every user are set automatically. However,
there are some commands that are hidden:

> ```
> /unlock <passwd> - Unlock bot functionalities with a password
> /get <config/cookies> - Retrieve config.json or cookies.json, respectively
> /update <config/cookies> - Update config.json or cookies.json, respectively
> /cancel - Cancel current update action
> ```

# Run
- Install python dependencies
  ```bash
  $ pip install -r requirements.txt
  ```
  > If you want to contribute, install development dependencies as well.
  > ```bash
  > $ pip install -r dev_requirements.txt
  > ```

- Create a self-signed certificate in order to communicate with telegram server using SSL
  ```bash
  $ openssl req -newkey rsa:2048 -sha256 -nodes -keyout config/nginx.key -x509 -days 3650 -out config/nginx.pem
  ```

- Create a directory named `config` to store bot configuration files.
Copy `templates/config.json` to `config` directory. Change values
according to your configuration.
  ```bash
  $ mkdir config
  $ cp templates/config.json config/config.json
  ```

  > **config.json**:
  > - **settings**:
  >   - **token** - Telegram bot token, obtained from
  >   [@BotFather](https://t.me/BotFather)
  >
  >   - **webhook**: `true` to run the bot using webhooks.
  >   `false` to use polling.
  >
  >   - **log_level**: set level of the logging module.
  >   More info: [log levels](https://docs.python.org/3/library/logging.html#logging-levels)
  >
  >   - **ip**: Your server/home IP. Must be accessible from internet.
  >
  >   - **port**: Port to receive telegram updates. Allowed ports: `443`, `80`, `88` and `8443`
  >     > Nginx can be used as reverse in order to use other ports.
  >     > Copy `templates/nginx.conf` to config and change values according
  >     > to your configuration.
  >     >
  >     > - `<docker-host-ip>` is the gateway of the containers. Looks like `172.17.0.1`
  >     > - `<portX>` Can be any port in the user range.
  >     ```bash
  >     $ cp templates/nginx.conf config/nginx.con
  >     $ docker run --rm --name nginx --net host -v ./config/nginx.conf:/etc/nginx/nginx.conf:ro -v ./config/nginx.key:/etc/nginx/nginx.key:ro -v ./config/nginx.pem:/etc/nginx/nginx.pem:ro nginx
  >     ```
  >
  >   - **cert**: Path to your server certificate (can be self-signed)
  >
  >   - **assemblyai_token**: Your AssemblyAI token, required to use ASR.
  >   More info: [Supported Languages](https://www.assemblyai.com/docs#supported-languages)
  >
  > - **chats**:
  >   - **password**: Password to use with /unlock and gain access to the
  >   bot (only required for the first time)
  >     ```json
  >     "password": "supersecurepassword123"
  >     ```
  >   - **id**: List of telegram IDs allowed in the bot, without password. Obtain
  >   if from bots like [@getmyid\_bot](https://t.me/getmyid_bot).
  >     ```json
  >     "id": [
  >         123123123,
  >         132322322
  >     ]
  >     ```
  >   - **admin**: List of telegram IDs allowed retrieve and update configuration files, i.e. config.json, cookies.json.
  >     ```json
  >     "admin": [
  >         123123123
  >     ]
  >     ```

- Run the bot.
  ```bash
  $ python src/edge.py
  ```

  > **Note:** If you run the bot in port 80, it may be needed to run the bot as
  > superuser (**sudo**)

# Docker
## Manual build
Build the image and bind `config` directory in the container
```bash
$ docker build . -t edgegpt-telegram-bot --rm
$ docker run -d -it --name edgegpt -v ./config:/edgegpt/config edgegpt-telegram-bot
```

## Dockerhub image
```bash
$ docker run -d -it --name edgegpt -v ./config:/edgegpt/config scmanjarrez/edgegpt-telegram-bot
```

> docker-compose.yml file provided.
> ```bash
> $ docker compose up -d
> ```

# Contributing
Happy to see you willing to make the project better. In order to make a contribution,
please respect the following format:
- Imports sorted with usort
  ```bash
  $ usort format *py
  ```
- Code formatted with black (line lenght 79)
  ```bash
  $ black -l 79 *py
  ```



> If you are using flake8, ignore E203 in .flake8
> ```
> [flake8]
> extend-ignore = E203
> ```

## Pre-commit hooks
Installation:
```bash
pre-commit install
```
Run manually:
```bash
pre-commit run --all-files
```

## VSCode project settings
VSCode should have the following settings in settings.json:
```
{
    "python.analysis.fixAll": [],
    "python.formatting.blackArgs": [
        "-l 79"
    ],
    "python.formatting.provider": "black",
    "isort.path": [
        "usort format"
    ],
}
```
> ```
> "python.linting.flake8Args": [
>     "--ignore=E203",
> ],
> ```

## Contributors
<a href="https://github.com/scmanjarrez/Edge-GPT-Telegram-Bot/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=scmanjarrez/Edge-GPT-Telegram-Bot"/>
</a>

# License
    Copyright (c) 2023 scmanjarrez. All rights reserved.
    This work is licensed under the terms of the MIT license.

For a copy, see
[LICENSE](LICENSE).
