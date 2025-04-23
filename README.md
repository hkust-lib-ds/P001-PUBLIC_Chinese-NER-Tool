[![DOI](https://zenodo.org/badge/807921510.svg)](https://doi.org/10.5281/zenodo.15266695)

_HKUST Library - DS CoLab Project - P001_
# Chinese Named-Entity Recognition (NER) Tool

**Project Introduction:**  https://library.hkust.edu.hk/ds/project/p001/  
**Timeframe:** 2023/24 Spring semester (Feb-May 2024)

## Preview

![preview of the app](manual-img/preview_DS-P001.png)

## Manual

+ [使用手冊 Manual Guide - manual.md](https://github.com/hkust-lib-ds/P001-PUBLIC_Chinese-NER-Tool/blob/main/manual.md)
+ [影片示範 Video Demo](https://library.hkust.edu.hk/ds/wp-content/uploads/2024/11/DS-P001_manual_video.mp4)

## Run our tool on your computer locally

1. **Ensure [python](https://www.python.org/downloads/) and [pip](https://pip.pypa.io/en/stable/installation/) are installed in your computer.**

> [!TIP]
> If you encounter difficulties in installing python and pip, please see slide 7-14 [here](https://digitalhumanities.hkust.edu.hk/tutorials/dive-deeper-into-python-and-streamlit-to-create-website-an-advanced-guide-with-demo-code-and-slides/#slides).

2. **Download our source code.**

   ```
   git clone https://github.com/hkust-lib-ds/P001-PUBLIC_Chinese-NER-Tool.git
   ```

3. **Change to the appropriate folder location.**
   ```
   cd P001-PUBLIC_Chinese-NER-Tool
   ```
   
4. **Install the required dependencies using the following command.**

    ```
    pip3 install -r requirements.txt
    ```

    OR

    ```
    pip install -r requirements.txt
    ```

5. **Run our tool using the following command.**

    ```
    streamlit run NER_Chinese.py
    ```

    OR

    ```
    python -m streamlit run NER_Chinese.py
    ```

> [!TIP]
> If you encounter difficulties in running the app, please read [this articles](https://digitalhumanities.hkust.edu.hk/tutorials/learn-python-from-zero-for-absolute-beginner-3-create-website/#view-locally) for reference.



## Project Team

| Developers          | Details                                    |
| :------------------ | :----------------------------------------- |
| YIP Sau Lai, Sherry | Year 3, BSc in Data Science and Technology |
| HAN Liuruo, Berry   | Year 2, BSc in Data Science and Technology |

| Advisers    | Details                                |
| :---------- | :------------------------------------- |
| Holly CHAN  | Assistant Manager (Digital Humanities) |
| Leo WONG    | Librarian (Systems & Digital Services) |
| Jennifer GU | Librarian (Research Support)           |
| Aster ZHAO  | Librarian (Research Support)           |
