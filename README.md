# Description
Telegram bot using [EdgeGPT](https://github.com/acheong08/EdgeGPT)
unofficial API

### What can I do?
- Access to Bing Chat without leaving your lovely messaging app!
- Change Bing Chat conversation styles
  > Do you want an original and imaginative response? (Creative style powered by gpt4)
  > Or more informative and friendly?
  > What about a more concise and straightforward answer?
- Start multiple conversations and switch between them
- Generate Images using Bing (powered by Dall-E)
- Text-to-speech responses (powered by edge-tts)
- Accept voice messages instead of text messages
  > Automatic-Speech-Recognition powered by AssemblyAI or Whisper (OpenAI)
- Configuration/cookie file download and update from the bot
- Restart the bot from your chat
- Inline queries to ask for questions or generate images
  > You can continue conversations from your private chat
- Enqueue queries. The bot will process each question in order
- Multi cookie management, stop hitting the daily limit!
- Permanent chat history (Recent activity in Bing)
- Export conversations

**Content**:
- [Description](#description)
  - [What can I do?](#what-can-i-do)
- [Features](#features)
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
- ffmpeg (only if you are using whisper)

# Bot commands
Commands available to every user are set automatically. However,
there are some commands that are hidden:

> ```
> /unlock <passwd> - Unlock bot functionalities with a password
> /get <config/cookies> - Retrieve config.json or cookies.json, respectively
> /update <config/cookies> - Update config.json or cookies.json, respectively
> /reset - Reload bot files
> /cancel - Cancel current update action
> ```

In order to use inline queries, you need to enable them in [@BotFather](https://t.me/BotFather).
For ease of use, use the placeholder
```
type text
```
Type can be **query** or **image**.

# Run
- Install python dependencies.
  ```bash
  $ pip install -r requirements.txt
  ```
  > If you want to contribute, install development dependencies as well.
  > ```bash
  > $ pip install -r dev_requirements.txt
  > ```

- Create a self-signed certificate in order to communicate with telegram server using SSL.
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
  >   [@BotFather](https://t.me/BotFather).
  >
  >   - **webhook**: `true` to run the bot using webhooks.
  >   `false` to use polling.
  >
  >   - **log_level**: set [level](https://docs.python.org/3/library/logging.html#logging-levels)
  >     of the logging module.
  >
  >   - **ip**: Your server/home IP. Must be accessible from internet.
  >
  >   - **port**: Port to receive telegram updates. Allowed ports: `443`, `80`, `88` and `8443`
  >     > Nginx can be used as a reverse proxy in order to use other ports.
  >     > Copy `templates/nginx.conf` to config and change values according
  >     > to your configuration.
  >     >
  >     > - `<docker-host-ip>` is the gateway of the container. Similar to `172.17.0.1`
  >     > - `<portX>` Can be any port in the user range.
  >     ```bash
  >     $ cp templates/nginx.conf config/nginx.con
  >     $ docker run --rm --name nginx --net host -v ./config/nginx.conf:/etc/nginx/nginx.conf:ro -v ./config/nginx.key:/etc/nginx/nginx.key:ro -v ./config/nginx.pem:/etc/nginx/nginx.pem:ro nginx
  >     ```
  >
  >   - **cert**: Path to your server certificate (can be self-signed).
  >     > Warning: If you're using a verified certificate, you may receive "certificate verify failed"
  >     error. Leave `cert` path empty in your config.json
  >
  > - **apis**:
  >   - **openai**: OpenAI token to use with whisper ([ASR](https://platform.openai.com/docs/guides/speech-to-text/supported-languages)),
  >     chatgpt/chatgpt4 and Dall-E (image generation).
  >   - **assemblyai**: AssemblyAI token ([ASR](https://www.assemblyai.com/docs#supported-languages)).
  >
  > - **chats**:
  >   - **password**: Password to use with /unlock and gain access to the
  >   bot (only required for the first time).
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
  >
  > - **cookies**: List of file paths to cookies
  >     ```json
  >     "cookies": [
  >         "config/cookies.json",
  >         "config/cookies2.json"
  >     ]
  >     ```

- Run the bot.
  ```bash
  $ chmod +x src/edge.py
  $ src/edge.py
  ```

  > **Note:** If you run the bot in port 80, it may be needed to run the bot as
  > superuser (**sudo**)

# Docker
## Manual build
Build the image and bind `config` directory in the container.
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
- Sort imports with `usort`.
  ```bash
  $ usort format *py
  ```
- Format your code using `black` (line length 79).
  ```bash
  $ black -l 79 *py
  ```

  > If you are using flake8, add E203 to .flake8 ignore list
  > ```
  > [flake8]
  > extend-ignore = E203
  > ```

## Pre-commit hooks
### Installation
```bash
$ pre-commit install
```

### Manual execution
```bash
$ pre-commit run --all-files
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
> If you use flake8, add:
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
