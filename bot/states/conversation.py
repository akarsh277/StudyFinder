from telegram.ext import ConversationHandler

# Conversation states for Upload Resource flow
SELECT_SEMESTER, SELECT_SUBJECT, SELECT_TYPE, ENTER_TITLE, UPLOAD_FILE = range(5)
