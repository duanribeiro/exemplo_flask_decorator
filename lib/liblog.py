class Bcolors:
    HEADER = '\033[95m'
    ITALIC = '\033[1;3m'
    OKBLUE = '\033[1;94m'
    OKGREEN = '\033[1;92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_red(text, flush=True):
    print(f"{Bcolors.FAIL}{text}{Bcolors.END}", flush=flush)
