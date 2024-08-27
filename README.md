# album-manager-googlephotos
Sync albums based on local folder structure

# Project relies on
* pyenv: https://github.com/pyenv/pyenv#installation
* poetry: https://python-poetry.org/

# Requirements
## Google Photos API
Follow instructions on https://developers.google.com/photos/library/guides/get-started. Store client credentials in project directory in file _client-secret.json_.

# After checkout run in project directory
```shell
pyenv versions
# install required version listed in .python-version
pyenv install 3.11.3
# restart shell
# install dependencies
poetry install
```

# Running script
```shell
poetry run push_local --help
```


# Example usage

Assumption is that you have folder tree structure, and folder represents album. Default folder naming is YYYY-MM-DD-Album name, flag --monthly_albums. This means that only the folders following this pattern will be uploaded, otherwise all folders will be created as albums.
```shell
poetry run push_local --help
# syncing just one year
poetry run push_local --verbose --local_album_path=/Users/user.name/Pictures/Albums --folder_prefix=2022
```

# Troubleshooting

- On first run, you should authenticate app with your gmail account to access your Google Photos. Credentials are stored locally. In case of getting error "token expired", just delete local file client_credentials.
- You can add photos to album only if photos are upload with this script. Re-upload doesn't help.
- If something happen during upload (error, network issue, exceeding quota), just repeat. Google Photos detects re-upload of media item (no duplicates). Maybe there would be an empty album. To prevent it, refresh album info, flag --refresh_albums.
- There is no delete on API, for deletion you have to do it manually in web app.