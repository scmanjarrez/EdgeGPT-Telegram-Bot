# Description
Telegram bot using [EdgeGPT](https://github.com/acheong08/EdgeGPT)
unofficial API

# Requirements
- python

# BotFather set up
Create a bot with [@BotFather](https://t.me/BotFather) and set the following commands:
```
new - Start a new conversation with the bot.
```

> Hidden commands:
> - /unlock \<passwd\> - Gain access to bot using a password

# Run
- Install python dependencies.

    `pip install -r requirements.txt`

- Create a self-signed certificate in order to communicate with telegram server using SSL.

    `openssl req -newkey rsa:2048 -sha256 -nodes -keyout ferdinand.key
    -x509 -days 3650 -out ferdinand.pem`

- Create a copy of config.template.json and change the dummy values in .config.json.

    `cp config.template.json .config.json`

    > - **token** - Telegram bot token, obtained from
    > [@BotFather](https://t.me/BotFather)
    >
    > - **webhook**: true to run the bot using webhooks. false to use polling.
    >
    > - **log_level**: set level of the logging module.
    > More info: [log levels](https://docs.python.org/3/library/logging.html#logging-levels)
    >
    > - **ip**: Your server ip, where the bot is hosted
    >
    > - **port**: Port to receive telegram updates: port must be 443, 80, 88 or 8443.
    >
    > - **cert**: Path to your server certificate (can be self-signed)
    >
    > - **password**: Password to use with /unlock and gain access to the
    > bot (only required for the first time)
    > ```json
    >    "password": "supersecurepassword123"
    > ```
    > - **id**: List of telegram IDs allowed in the bot, without password. Obtain
    > if from bots like [@getmyid\_bot](https://t.me/getmyid_bot).
    > ```json
    >    "ids": [
    >        123123123,
    >        132322322
    >    ]
    > ```

- Execute the bot.

    `./edge.py`

    > **Note:** If you run the bot in port 80, it may be needed to run the bot as
    > superuser (**sudo**).

# Contributing
Happy to see you willing to make the project better. In order to make a contribution,
please respect the following format:
- Imports sorted with usort: `usort format <file>`
- Code formatted with black (line lenght 79): `black -l 79 <file>`

> If you are using flake8, ignore E203 in .flake8
> ```
> [flake8]
> extend-ignore = E203
> ```

### VSCode project settings
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

# License
    Copyright (c) 2023 scmanjarrez. All rights reserved.
    This work is licensed under the terms of the MIT license.

For a copy, see
[LICENSE](LICENSE).
