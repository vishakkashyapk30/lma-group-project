# DOCX layout

There is no `.docx` template file: the generic High Court format (plan §8.2) is built in code, so every heading, placeholder and table can be tested.

- `export/docx_style.py`: page size, fonts, the "AI-generated draft: check against your court's rules." banner in the header, the draft label and page number in the footer, headings and tables.
- `export/application.py`: the application's eleven sections in the order of `export/sections.py`.
- `export/list_of_dates.py`: the List of Dates and Events, inside the application and as its own file.

Court-specific formats are out of scope for v5 (plan §20); one would be a new layout module next to `application.py`.
