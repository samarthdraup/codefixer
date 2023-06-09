import tkinter as tk
from tkinter import ttk
import json
import re
import openai
import time
import difflib
import os
import datetime


def save_dict_to_csv_file(data, model_name):
    """
    Save the dictionary to a csv file
    Args: data: dict
    Returns: None
    """
    if not os.path.exists('data.csv'):
        with open('data.csv', 'w', encoding="utf8") as f:
            f.write("prompt token,completion token, model, datetime\n")
    with open('data.csv', 'a', encoding="utf8") as f:
        f.write(f"{data['prompt_tokens']},{data['completion_tokens']},{model_name},{datetime.datetime.now()}\n")



def get_updated_code(prompt):
    """
    Get the updated code from GPT-4 API
    Args: prompt: str
    Returns: str
    """

    # Set up the OpenAI API credentials
    openai.api_key = os.environ.get("OPENAI_API_KEY_4")
    model_engine = "gpt-4"
    start_time = time.time()
    # Generate corrected code using GPT-3.5 API
    response = openai.ChatCompletion.create(
        model=model_engine,
        messages=[
            {"role": "system",
             "content": "You are a automated ai python code fixer that takes partial python code and fixes it without giving explanation and  without changing starting code or ending code. and i strictly want python code inside <python> </python>"},
            {"role": "user", "content": prompt}
        ]
    )
    end_time = time.time()
    response_time = end_time - start_time
    # print(response)
    save_dict_to_csv_file(response["usage"], response['model'])
    # Extract the corrected code from the response
    corrected_code = response.choices[0].message.content.strip()
    print(corrected_code)
    # extract code inside \n\n use regex

    code_pattern = re.compile(r'```(.*?)```', re.DOTALL)
    code_matches = code_pattern.findall(corrected_code)
    # extract code inside <python> <python> use regex
    if not code_matches:
        code_matches = corrected_code
    else:
        code_matches = code_matches[0]

    code_pattern_2 = re.compile(r'<python>(.*?)</python>', re.DOTALL)
    code_matches_2 = code_pattern_2.findall(code_matches)
    if not code_matches_2:
        code_matches_2 = code_matches
    else:
        code_matches_2 = code_matches_2[0]
    if 'code' in code_matches_2:
        code_matches_2 = code_matches_2[code_matches_2.find('code:') + len('code:'):]
    return code_matches_2, response_time



def get_sonar_report_data(filename='sonarqube_bugs.json'):
    """
    Get the sonarqube report data from the json file in required format
    Args: filename: str
    Returns: list of dict
    """

    # Open the file and read its contents
    with open(filename, 'r', encoding="utf8") as file:
        data = json.load(file)
    # Extract the data we want
    all_data = []
    for issue in data['issues']:
        d = {}
        try:
            component = issue['component']
            d['file_path'] = component.split(':')[-1]
            d['start_line'] = issue['textRange']['startLine']
            d['end_line'] = issue['textRange']['endLine']
            d['message'] = issue['message']
            all_data.append(d)
        except:
            pass
    return all_data


def get_new_block_as_string(file_path, start_line, end_line):
    """
    Get the complete function or class which encloses the bug,
    But limits the search to 10 lines before the start_line and 5 lines after the end_line
    Args: file_path: str
          start_line: int
          end_line: int
    Returns: code: str
             start_index: int
             end_index: int
             start_statement: str
             end_statement: list of str
            start_indent: int
    """

    backward_search_limit = 5
    forward_search_limit = 5
    # Open the file and read its contents
    with open(file_path, 'r', encoding="utf8") as file:
        lines = file.readlines()

    # Search backwards from start_line to find the start of the function or class
    start_index = None
    lines_searched = 0
    if lines[start_line - 1].lstrip().startswith(('def ',)):
        start_index = start_line - 1
    for i in range(start_line - 2, max(start_line - backward_search_limit - 1, -1), -1):
        if start_index is not None:
            break
        lines_searched += 1
        line = lines[i]
        if line.lstrip().startswith(('if', 'for', 'def ', 'try', 'while', 'Class ')):
            start_index = i
            break

    if start_index is None:
        start_index = max(start_line - lines_searched, 0)

    # Search forwards from end_line to find the return statement till forward_search_limit
    end_index = None
    lines_searched = 0
    for i in range(end_line + 1, min(end_line + forward_search_limit + 1, len(lines))):
        lines_searched += 1
        line = lines[i]
        if line.lstrip().startswith(('return ',)):
            end_index = i
            break
    if end_index is None:
        end_index = min(end_line + forward_search_limit, len(lines))

    start_statement = lines[start_index].strip()
    while not start_statement.strip() and start_index < end_index:
        start_statement = lines[start_index].strip()
        start_index += 1

    return ''.join(lines[start_index:end_index+1]), start_index, end_index


def update_line_number(msg, new_line):
    """
    update line number in message according to the new code
    Args: msg: str
          new_line: int
    Returns: str
    """
    pattern = r"(line )(\d+)"
    regex = re.compile(pattern)

    replacement_str = r"\g<1>{}".format(new_line)

    new_text = regex.sub(replacement_str, msg)
    return new_text + f"Line {new_line}"


def write_updated_code_to_file(file_path, code, prev_code=None):
    """
    Write the updated code to the file
    Args: file_path: str
          start_line: int
          end_line: int
          code: str
    Returns: None
    """

    # read the file
    with open(file_path, 'r', encoding="utf8") as file:
        lines = file.readlines()

    # remove code from start_line to end_line
    # start_line and end_line are code in the file
    # add a comment in place of start_line saying bug fixed
    print("prev_code :\n", prev_code)
    print('before indentation')
    print("code :\n", code)
    # get the index of code that matches line 1 , and next 2 lines should match line 2 and line 3
    prev_code = prev_code.split('\n')
    start_index = None
    for i in range(len(lines)):
        if lines[i].strip() == prev_code[0].strip()  and lines[i+1].strip() == prev_code[1].strip() and lines[i+2].strip() == prev_code[2].strip():
            start_index = i
            break

    end_index = start_index + len(prev_code) - 1

    # GET THE INDENTATION OF THE start_line is string of code
    start_indent = len(lines[start_index]) - len(lines[start_index].lstrip())
    # add indentation to the comment
    comment = " " * start_indent + "# Bug fixed\n"
    # add indentation to the updated code
    code = code.split('\n')
    code = [" " * start_indent + i for i in code]

    # combine the comment and the updated code
    code = comment + '\n'.join(code)
    # get empty lines from prev_code at the end

    print('after indentation')
    print("code:\n", code)

    # count the number of empty lines at the end of prev_code
    # it should not count empty lines in the middle of the code
    empty_lines = 0
    for i in range(len(prev_code) - 1, -1, -1):
        if prev_code[i].strip():
            break
        empty_lines += 1

    # add empty lines at the end of the updated code
    code = code + '\n' * empty_lines
    # replace the code with the updated code and retain \n at the end of the line
    lines[start_index:end_index] = [code + '\n' for code in code.split('\n')]
    # write the updated code to the file
    with open(file_path, 'w', encoding="utf8") as file:
        file.writelines(lines)

    return


class CodeFixerUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Code Fixer")

        # Create the main frame
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create the label and text widget for previous code
        self.prev_code_label = ttk.Label(self.main_frame, text="Previous Code:")
        self.prev_code_label.grid(row=2, column=0, sticky=(tk.W, tk.N))
        self.prev_code_text = tk.Text(self.main_frame, wrap=tk.NONE, height=20, width=50)
        self.prev_code_text.grid(row=3, column=0, padx=(0, 10), sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create the label and text widget for updated code
        self.updated_code_label = ttk.Label(self.main_frame, text="Updated Code:")
        self.updated_code_label.grid(row=2, column=1, sticky=(tk.W, tk.N))
        self.updated_code_text = tk.Text(self.main_frame, wrap=tk.NONE, height=20, width=50)
        self.updated_code_text.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.message_label = ttk.Label(self.main_frame, text="SonarQube Message:")
        self.message_label.grid(row=0, column=0, sticky=(tk.W, tk.N))
        self.message_text = tk.Text(self.main_frame, wrap=tk.WORD, height=2)
        self.message_text.grid(row=1, column=0, columnspan=2, padx=(0, 0), sticky=(tk.W, tk.E, tk.N, tk.S))

        self.response_time_text = tk.Text(self.main_frame, wrap=tk.WORD, height=1)
        self.response_time_text.grid(row=4, column=0, columnspan=3, padx=(0, 0), sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create the buttons
        self.ignore_button = ttk.Button(self.main_frame, text="Ignore", command=self.ignore_bug)
        self.ignore_button.grid(row=6, column=0, columnspan=1, pady=(10, 0), padx=(5, 5), sticky=(tk.W, tk.E))

        self.fix_button = ttk.Button(self.main_frame, text="Fix", command=self.fix_bug)
        self.fix_button.grid(row=5, column=0, pady=(10, 0), padx=(5, 5), sticky=(tk.W, tk.E))

        self.retry_button = ttk.Button(self.main_frame, text="Retry", command=self.retry)
        self.retry_button.grid(row=5, column=1, columnspan=1, pady=(10, 0), padx=(5, 5), sticky=(tk.W, tk.E))

        self.diff_button = ttk.Button(self.main_frame, text="Show Diff", command=self.highlight_differences)
        self.diff_button.grid(row=6, column=1, columnspan=1, pady=(10, 0), padx=(5, 5), sticky=(tk.W, tk.E))

        # Configure the column and row weights
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # Initialize data and current bug index
        self.data = get_sonar_report_data()
        self.current_bug_index = 0
        self.path = None

        if os.environ.get("PRECOMPUTE") == "YES":
            self.precompute_all_suggestions()
        else:
            # Load the first bug on application start
            global code_data
            self.code_data = self.process_bug()

    def highlight_differences(self):
        content1 = self.prev_code_text.get('1.0', tk.END).splitlines()
        content2 = self.updated_code_text.get('1.0', tk.END).splitlines()

        d = difflib.Differ()
        diff = list(d.compare(content1, content2))

        self.prev_code_text.configure(state='normal')
        self.updated_code_text.configure(state='normal')

        self.prev_code_text.tag_remove('removed', '1.0', tk.END)
        self.updated_code_text.tag_remove('added', '1.0', tk.END)

        for i, line in enumerate(diff):
            if line.startswith('-'):
                pos = content1.index(line[2:])
                if pos != -1:
                    line_num = pos + 1
                    self.prev_code_text.tag_add('removed', f'{line_num}.0', f'{line_num}.end')
            elif line.startswith('+'):
                pos = content2.index(line[2:])
                if pos != -1:
                    line_num = pos + 1
                    self.updated_code_text.tag_add('added', f'{line_num}.0', f'{line_num}.end')
            else:
                pass
        # Configure the tags for the added and removed code
        self.prev_code_text.tag_configure('removed', background='lightcoral')
        self.updated_code_text.tag_configure('added', background='lightgreen')

    def retry(self):
        suggested_code = self.code_data[1]
        self.process_bug(suggested_code)
        return

    def ignore_bug(self):
        # Ignore the bug and move to the next bug
        self.current_bug_index += 1
        self.process_bug()
        return

    def fix_bug(self):
        # Fix the bug and move to the next bug
        updated_code = self.updated_code_text.get(1.0, tk.END)
        code = self.code_data[0]
        # add processing txt to in updated window
        self.updated_code_text.delete(1.0, tk.END)
        self.updated_code_text.insert(1.0, 'Processing...')
        write_updated_code_to_file(self.path, updated_code, prev_code=code)
        # add status to the updated window
        self.updated_code_text.delete(1.0, tk.END)
        self.updated_code_text.insert(1.0, 'Fixed')
        self.current_bug_index += 1
        self.process_bug()
        return

    def write_precomputed_suggestions_to_file(self):
        # self.data is a list of dictionaries, write it to a json file
        with open('precomputed_suggestions.json', 'w', encoding="utf8") as f:
            json.dump(self.data, f)

    def precompute_all_suggestions(self):
        if os.environ.get('PRECOMPUTED') == 'NO':
            for d in self.data:
                path = os.environ.get('CODE_PATH') + d['file_path']
                code, start_index, end_index = \
                    get_new_block_as_string(path, d['start_line'], d['end_line'])
                fix_msg = d['message']
                fix_msg = update_line_number(fix_msg, d['start_line'] - start_index)
                msg = f"""Here's a partial Python code with a bug inside <python> </python>:
                            code: \n {code} \n 
                            line number: {d['start_line'] - start_index}
                            message: {fix_msg}
                            Strictly follow the following
                            instructions:
                            * Use message to get the context of the bug
                            * Fix the bug
                            * don't include any explanation 
                            * correct the indentation before sending the code
                            * send code inside code block
                            response format : 
                            <python>
                            print('hello world')
                            </python>
                            """
                updated_code, response_time = get_updated_code(msg)
                d['suggested_code'] = updated_code
                d['response_time'] = response_time
            self.write_precomputed_suggestions_to_file()

        global code_data
        self.code_data = self.process_bug()

    def get_data_from_precomputed_file(self):
        with open('precomputed_suggestions.json', 'r', encoding="utf8") as f:
            data = json.load(f)
        return data

    def process_bug(self, wrong_code=None):
        if self.current_bug_index < len(self.data):
            # add fetching message to the both windows
            self.prev_code_text.delete(1.0, tk.END)
            self.prev_code_text.insert(1.0, 'Fetching...')
            self.updated_code_text.delete(1.0, tk.END)
            self.updated_code_text.insert(1.0, 'Fetching...')
            if os.environ.get('PRECOMPUTE') == 'YES':
                self.data = self.get_data_from_precomputed_file()
            d = self.data[self.current_bug_index]
            self.path = os.environ.get('CODE_PATH') + d['file_path']
            code, start_index, end_index = \
                get_new_block_as_string(self.path, d['start_line'], d['end_line'])
            wrong_suggestion_message = None
            if wrong_code:
                wrong_suggestion_message = """
                last time you sent wrong suggestion 
                suggested code : {wrong_code}
                """
            fix_msg = d['message']
            fix_msg = update_line_number(fix_msg, d['start_line'] - start_index)
            if wrong_code:
                fix_msg = self.message_text.get(1.0, tk.END)
            msg = f"""Here's a partial Python code with a bug inside <python> </python>:
            code: \n {code} \n 
            line number: {d['start_line'] - start_index}
            message: {fix_msg}
            Strictly follow the following
            instructions:
            * Use message to get the context of the bug
            * Fix the bug
            * don't include any explanation 
            * correct the indentation before sending the code
            * send code inside code block
            response format : 
            <python>
            print('hello world')
            </python>
            {str(wrong_suggestion_message) if wrong_suggestion_message else ''}
            """
            if wrong_code:
                updated_code, response_time = get_updated_code(msg)  # Display the previous code in the UI
            else:
                if os.environ.get('PRECOMPUTE') == 'YES':
                    updated_code, response_time = d['suggested_code'], d['response_time']
                else:
                    updated_code, response_time = get_updated_code(msg)
            print("-----old code-----")
            print(code)
            print("-----new code-----")
            print(updated_code)
            temp_prev_code = code.split('\n')
            # get the smallest indentation in temp_prev_code
            indentation = 100000
            for line in temp_prev_code:
                if line.strip() != '':
                    indentation = min(indentation, len(line) - len(line.lstrip()))
            # remove indentation from all lines
            for i in range(len(temp_prev_code)):
                temp_prev_code[i] = temp_prev_code[i][indentation:]

            temp_new_code = updated_code.split('\n')
            # remove empty lines from start and end
            while temp_new_code[0] == '':
                temp_new_code.pop(0)
            while temp_new_code[-1] == '':
                temp_new_code.pop(-1)
            # get smallest indentation in temp_new_code
            indentation = 100000
            for line in temp_new_code:
                if line.strip() != '':
                    indentation = min(indentation, len(line) - len(line.lstrip()))
            # remove indentation from all lines
            for i in range(len(temp_new_code)):
                temp_new_code[i] = temp_new_code[i][indentation:]
            temp_new_code = '\n'.join(temp_new_code)

            if wrong_code:
                fix_msg_to_display = fix_msg
            else:
                fix_msg_to_display = fix_msg + '\n' + (code.split('\n')[d['start_line'] - start_index - 1]).lstrip()

            temp_prev_code = '\n'.join(temp_prev_code)
            self.prev_code_text.delete(1.0, tk.END)
            self.prev_code_text.insert(tk.END, temp_prev_code)
            # Display the updated code in the UI
            self.updated_code_text.delete(1.0, tk.END)
            self.updated_code_text.insert(tk.END, temp_new_code)

            self.message_text.delete(1.0, tk.END)
            self.message_text.insert(1.0, fix_msg_to_display)

            self.response_time_text.delete(1.0, tk.END)
            # fomat the response time to 4 decimal places
            response_time = "{:.4f}".format(response_time)
            self.response_time_text.insert(1.0, f"Response Time: {response_time} sec")

            self.code_data = (code, updated_code)
            self.highlight_differences()
            return self.code_data
        else:
            # Display a message when there are no more bugs
            self.prev_code_text.delete(1.0, tk.END)
            self.updated_code_text.delete(1.0, tk.END)
            self.message_text.delete(1.0, tk.END)
            self.response_time_text.delete(1.0, tk.END)
            self.prev_code_text.insert(tk.END, "No more bugs to process")
            self.updated_code_text.insert(tk.END, "No more bugs to process")
            self.message_text.insert(tk.END, "No more bugs to process")
            self.response_time_text.insert(tk.END, "No more bugs to process")

def main():
    root = tk.Tk()
    app = CodeFixerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
