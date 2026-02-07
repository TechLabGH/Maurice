# Maurice

![Maurice](Code/L_maurice.png)

Python task scheduler with GUI.
Resides in system tray and runs python scripts based on Daily / Weekly and Monthly frequency.

### Version: 1.0

## What works:
- GUI
- adding and deleting tasks

## ToDo:
- running tasks

## Tested with Python 3.13

Program is running on background and controlls running python scripts based on programmed schedule.
It minimalize to system tray so it can't be accidentally closed.

## Add new task
	Fill out fields on right side with following info
	- Name - Needs to be unique
	- Frequency - select Daily / Weekly / Monthly
	- Start - Provide first run datetime in format YYYY-MM-DD HH:MM. This is when task will be 
		executed first time, next run will be determined based on selected frequency.
		THIS DATETIME NEEDS TO BE IN THE FUTURE
	- Path - select py or pyw file that should be executed
	- Click [Save] - new task should be visible now in selection box on left

## Reviewing tasks
	Select task on left side to see it's schedule and config
	Selected task can't be edited, you need to delete it and re-configure again.
	
## Closing program
	Maurice will minimalize to system tray as default when [X] or [-] buttons are clicked.
	Use Menu -> File -> Exit or right click on tray icon and [Exit] to close program.

## Errors

### Schedule file is empty or has broken structure
Ignore if you didn't schedule any task yet. If you have tasks configured, check schedules.json file.
It should have following structure

```json
[
  {
    "name": "Test",
    "frequency": "Weekly",
    "next_run": "2026-03-01 01:00",
    "filepath": "C:/Users/User/Scripts/test.py",
    "last_run": "1900-01-01 00:00"                  << this date indicates that task was never executed yet
  },
  {
    "name": "Test2",
    "frequency": "Monthly",
    "next_run": "2027-01-01 06:00",
    "filepath": "C:/Users/User/Scripts/test2.py",
    "last_run": "1900-01-01 00:00"
  }
]
```

### Schedule file not found
Make sure, there is schedules.json file in program's folder. Create it, if missing and init with [] brackets.
