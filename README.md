
# Maurice

<div align="center">
	
![Maurice](Code/L_maurice.png)

</div>

Python task scheduler with GUI.
Resides in system tray and runs python scripts based on Daily / Weekly and Monthly frequency.

### Version: 2.1

## Main functionality
- [x] GUI
- [x] Closes and minimalize to system tray
- [x] No installation, no admin rights needed
- [x] Easy adding and deleting tasks
- [x] Running missed tasks on start

## Tested with Python 3.13

Program is running on background and controlls running python scripts based on programmed schedule.
It minimalize to system tray so it can't be accidentally closed.

## Add new task

Fill out fields on right side with following info
- Name - Needs to be unique
- Frequency - select Daily / Weekly / Monthly
- Start - Provide first run datetime in format YYYY-MM-DD HH:MM. This is when task will be executed first time, next run will be determined based on selected frequency. ** THIS DATETIME NEEDS TO BE IN THE FUTURE **
- Path - select py or pyw file that should be executed
- Click [Save] - new task should be visible now in selection box on left

## Reviewing tasks

Select task on left side to see it's schedule and config. Selected task can't be edited, you need to delete it and re-configure again.
	
## Closing program
	
Maurice will minimalize to system tray as default when [X] or [-] buttons are clicked. Use Menu -> File -> Exit or right click on tray icon and [Exit] to close program.

## Errors

>[!CAUTION]
>schedules.json is invalid JSON. Fix it or recreate it.

schedules.json should have following structure

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

Delete file if this is broken. Program will recreate it so you can add tasks back.
</br></br>
>[!CAUTION]
>Please fill in all fields.

All fields (Name, Frequency, Start, path) needs to be filled so task can be added
</br></br>
>[!CAUTION]
>Start time must match...

Make sure, that start datetime match YYYY-MM-DD HH:MM format
</br></br>
>[!CAUTION]
>Start time must be in the future

Next run datetime needs to be in the future.
</br></br>
>[!CAUTION]
>Selected script path does not exist

Error may show up, if you pasted path and it can't be found.
</br></br>
>[!CAUTION]
>A task with that name already exists

Name should be unique so they are easier to ideantify later. While name is not used in running task, error was added to avoid adding multiple tasks with the same names.
</br></br>
>[!CAUTION]
>Failed to save schedules.json / Failed to update schedules.json

This may happen for example if remote location, where program is saved was disconnected
</br></br>
>[!CAUTION]
>No task selected

You accidentally pressed Delete button while no task was selected.



## FAQ
**Why is the program called Maurice?**

Because even someone as great as King Julien needs helpers to take care of boring tasks. 🙂

And seriously—it’s just a bit of internal, family humor.
