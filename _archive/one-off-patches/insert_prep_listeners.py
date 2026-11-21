with open('web/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the agenda-close event listener
insert_idx = None
for i, line in enumerate(lines):
    if '$("agenda-close").addEventListener("click"' in line:
        insert_idx = i + 1
        break

if insert_idx is None:
    print("Could not find insertion point")
    exit(1)

new_code = [
    '  $("prep-work-close").addEventListener("click", closePrepWorkModal);\n',
    '  $("prep-work-cancel").addEventListener("click", closePrepWorkModal);\n',
    '  $("prep-work-modal").addEventListener("click", (event) => { if (event.target === $("prep-work-modal")) closePrepWorkModal(); });\n',
    '  $("prep-work-form").addEventListener("submit", savePreparationWork);\n',
    '  $("prep-work-destination").addEventListener("change", () => {\n',
    '    const isProgram = $("prep-work-destination").value === "program";\n',
    '    $("prep-work-event-wrap").classList.toggle("hidden", !isProgram);\n',
    '    $("prep-work-date-wrap").classList.toggle("hidden", !isProgram);\n',
    '  });\n',
    '  $("prep-work-files").addEventListener("change", (event) => {\n',
    '    const files = Array.from(event.target.files || []);\n',
    '    files.forEach((file) => {\n',
    '      const purpose = detectFileType(file);\n',
    '      prepWorkFiles.push({file, name: file.name, part_label: null, purpose});\n',
    '    });\n',
    '    renderPrepWorkFiles();\n',
    '    event.target.value = "";\n',
    '  });\n',
    '  $("repertoire-add").addEventListener("click", openPrepWorkModal);\n',
    '\n',
]

# Insert after agenda-close
lines = lines[:insert_idx] + new_code + lines[insert_idx:]

with open('web/app.js', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Inserted prep work event listeners')