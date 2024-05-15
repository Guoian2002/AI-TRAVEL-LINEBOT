import opencc

s2t_converter = opencc.OpenCC('s2t')
t2s_converter = opencc.OpenCC('t2s')


def get_role_and_content(response: str):
    role = response['message']['role']
    content = response['message']['content'].strip()
    content = s2t_converter.convert(content)
    return role, content
