from homeassistant.backports.enum import StrEnum

STARTUP = """
                _
     /\        | |
    /  \  _   _| | __ _
   / /\ \| | | | |/ _` |
  / ____ \ |_| | | (_| |
 /_/    \_\__,_|_|\__,_|
Aula integration, version: %s
This is a custom integration
If you have any issues with this you need to open an issue here:
https://github.com/scaarup/aula/issues
-------------------------------------------------------------------
"""

DOMAIN = "aula"
API = "https://www.aula.dk/api/v"
API_VERSION = "17"
MIN_UDDANNELSE_API = "https://api.minuddannelse.net/aula"
MEEBOOK_API = "https://app.meebook.com/aulaapi"
SYSTEMATIC_API = "https://systematic-momo.dk/api/aula"
CONF_SCHOOLSCHEDULE = "schoolschedule"
CONF_UGEPLAN = "ugeplan"


class Widget(StrEnum):
	AbsenceParentReporting = "0047"
	MinUddannelseTasks = "0030"
	MinUddannelseSchedule = "0029"
	MeebookSchedule = "0004"
	SystematicTodo = "0062"
	Library = "0019"
