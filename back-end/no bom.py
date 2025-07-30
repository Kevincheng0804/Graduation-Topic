import json

input_file = 'C:\\Users\\davis\\專研\\Graduation-Topic\\後端\\valdata.jsonl'
output_file = 'C:\\Users\\davis\\專研\\Graduation-Topic\\後端\\valdata_utf8_no_bom.jsonl'

try:
    # 假設原始檔案是以 UTF-8 讀取（或可以成功讀取）
    with open(input_file, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()

    with open(output_file, 'w', encoding='utf-8', newline='') as outfile: # newline='' 很重要
        for line in lines:
            # 寫入時，Python 的 utf-8 編碼通常不帶 BOM
            # newline='' 確保不會在每行結尾額外添加 Windows 風格的 \r\n
            outfile.write(line)

    print(f"File '{input_file}' processed and saved as UTF-8 (likely without BOM) to '{output_file}'.")

except Exception as e:
    print(f"An error occurred during UTF-8 processing: {e}")