# Nuitka-winsvc User Manual

Nuitka-winsvc is a forked version of Nuitka, it supports compiling EXE as a Windows service. 

## Install

You can install Nuitka-winsvc by pip: 

```shell
pip install nuitka-winsvc
```

## Usage

In addition to supporting all the command line arguments of Nuitka, Nuitka-winsvc also provides 5 additional arguments for compiling the Windows services:

- `--windows-service`  
  Enable Windows service mode, works only when compiling for Windows and onefile mode enabled.
- `--windows-service-name`  
  Name of the Windows service. If not provided, the target program name will be used as the service name.
- `--windows-service-display-name`  
  Display name of the Windows service. If not provided, the product name will be attempted to use.
- `--windows-service-description`  
  Description of the Windows service. If not provided, the file description will be attempted to use.
- `--windows-service-cmdline`  
  Additional command line arguments that will be passed to the Windows service. Just like `--config config.json --output output.log` .

Use the following command to build a Windows service:

```shell
python -m nuitka --onefile --output-dir=build --windows-service --windows-service-name=myservice --windows-service-display-name="My Service" --windows-service-description="This is the description of my service" --windows-service-cmdline="-c config.yml -o output.log" main.py
```

When the python program is compiled successfully, you can use the following command to install the service:

```shell
.\main.exe install
```

Also you can use the following command to install the service:

```shell
.\main.exe uninstall
```

Note: Administrator privileges is required when installing and uninstalling the Windows services. You should run the above commands as administrator. 

