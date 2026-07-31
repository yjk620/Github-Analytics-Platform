# Grab the two tools we need from the pydantic_settings library.
from pydantic_settings import BaseSettings, SettingsConfigDict

# This class lists every config value our app needs to run.
# Because it's built on BaseSettings (not a plain class), it knows how to
# fill in those values by itself - by looking at environment variables -
# instead of us typing them in by hand.
class Settings(BaseSettings):
    # By itself, BaseSettings only looks at real environment variables set on
    # your computer - it won't peek inside a .env file on its own. This line
    # tells it "also check the .env file sitting next to this script."
    model_config = SettingsConfigDict(env_file=".env")

    # We need a value called test_value, and it must be text (a string).
    # BaseSettings will look for an env var with a matching name (TEST_VALUE)
    # and put its value here. If TEST_VALUE doesn't exist, or isn't text,
    # this whole file will crash with an error as soon as it runs - which is
    # what we want, so we notice the problem immediately instead of later.
    test_value: str
    database_url: str

# This is the line that actually does the work: it reads .env, finds
# TEST_VALUE, checks it's text, and builds a `settings` object holding it.
# Any other file in the project can import `settings` to get these values.
settings = Settings()

##################FLOW################
#1. import the necessary libraries from pydantc settings
#2. define a new class called Settings
  #checks over the enviornmental data through BaseSettings
  #goes over .env thorugh SettingsConfigDict 
    #when going over .env we check if the test_values are in text, string
#3. Then we call Setting() into vairbale settings 
  #when we import the class in a different file we can read the finalized test_value object