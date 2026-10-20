from telegram.ext import ConversationHandler

# Conversation states for Upload Resource flow
SELECT_SEMESTER, SELECT_SUBJECT, SELECT_TYPE, ENTER_TITLE, UPLOAD_FILE = range(5)

# Conversation state for Rename Resource flow
RENAME_TITLE = 10
