# Desktop Launcher

This folder contains a lightweight Windows launcher and installer for the shared register.

## Files

- `FirstRespondersLauncher.exe`: opens the configured URL in the default browser
- `FirstRespondersLauncherInstaller.exe`: installs the launcher into the user's local profile and creates shortcuts
- `launcher-url.txt`: the URL the launcher opens

## Build

The exes are compiled locally from:

- `FirstRespondersLauncher.cs`
- `FirstRespondersLauncherInstaller.cs`

## Install flow

1. Set the correct shared app URL in `launcher-url.txt`
2. Run `FirstRespondersLauncherInstaller.exe`
3. The installer copies the launcher to `%LOCALAPPDATA%\FirstRespondersRegisterLauncher`
4. It creates a Desktop shortcut and a Startup shortcut

When the user logs in, Windows will run the shortcut in Startup, which opens the shared register URL in the default browser.
