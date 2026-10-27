from telegram.ext import ConversationHandler

# Conversation states for Upload Resource flow
SELECT_BRANCH, SELECT_SEMESTER, SELECT_SUBJECT, SELECT_TYPE, ENTER_TITLE, UPLOAD_FILE = range(6)

# Conversation state for Rename Resource flow
RENAME_TITLE = 10

# Conversation state for Add Branch flow (Chief only)
ENTER_BRANCH_NAME = 20

