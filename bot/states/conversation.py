from telegram.ext import ConversationHandler

# Conversation states for Upload Resource flow
SELECT_BRANCH, SELECT_SEMESTER, SELECT_SUBJECT, SELECT_TYPE, ENTER_TITLE, UPLOAD_FILE = range(6)

# Conversation state for Rename Resource flow
RENAME_TITLE = 10

# Conversation state for Add Branch flow (Chief only)
ENTER_BRANCH_NAME = 20

# Conversation states for Add Semester flow (Chief only)
SELECT_BRANCH_FOR_SEM, ENTER_SEM_NAME = 30, 31

# Conversation states for Add Subject flow (Chief only)
SELECT_BRANCH_FOR_SUBJ, SELECT_SEM_FOR_SUBJ, ENTER_SUBJ_NAME = 40, 41, 42


