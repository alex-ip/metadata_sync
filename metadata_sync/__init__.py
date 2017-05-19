import sys
import logging

# Set handler for root logger to standard output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logging.root.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module
