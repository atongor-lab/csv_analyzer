import streamlit as st
import pandas as pd
import csv
import chardet
import plotly.express as px
import plotly.graph_objects as go

@st.cache_data(show_spinner="Определение разделителя и кодировки...")
def most_posible_sep_and_enc(file_bytes: bytes):
    detection_result = chardet.detect(file_bytes)
    encoding = detection_result["encoding"]
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(file_bytes.decode(f"{encoding}"))
    detected_sep = dialect.delimiter
    return detected_sep, encoding

@st.cache_data(show_spinner="Загрузка таблицы")
def safe_load_table(file: bytes, detected_sep: str = ",", encoding: str = "utf-8"):

    df = None
    if file.name.endswith(".csv"):
        file.seek(0)
        df = pd.read_csv(file, encoding=encoding, sep=detected_sep, index_col=False)
        for col in df.select_dtypes(include=['object']).columns:
            possible_datetime = pd.to_datetime(df[col], errors='coerce')
            if possible_datetime.notna().mean() > 0.8:
                df[col] = possible_datetime
    return df

def plot_and_download(figure: go.Figure, label: str):

    img_bytes = figure.to_image(format="png", scale=3)
    st.plotly_chart(figure)
    st.download_button(
        label="💾 Сохранить график",
        data=img_bytes,
        file_name=f"{label}.png",
        mime="image/png",
    )

def main():

    st.set_page_config(
        page_title="Анализатор .csv файлов",
        page_icon="📋",
        layout="wide",
    )
    with st.sidebar:
        st.header("📂 Открыть файл")
        file = st.file_uploader("Загрузите файл с таблицей", type=["csv"])
        if file is None:
            st.stop()
        file_bytes = file.getvalue()[:100000]
        try:
            if "detected_sep" not in st.session_state or "encoding" not in st.session_state:
                detected_sep, encoding = most_posible_sep_and_enc(file_bytes)
                st.session_state["detected_sep"] = detected_sep
                st.session_state["encoding"] = encoding
            df = safe_load_table(file, st.session_state.detected_sep, st.session_state.encoding)
        except pd.errors.EmptyDataError:
            st.error('Файл пустой!')
            st.stop()
        except:
            st.error(
                "Не удалось определить кодирование или разделитель автоматически, попробуйте переопределить вручную"
            )
        custom_sep = st.text_input("Переопределить разделитель", value=",")
        custom_enc = st.text_input("Переопределить кодировку", value="utf-8")
        custom_btn_pressed = st.button("Переопределить")
        if custom_btn_pressed:
            st.session_state["detected_sep"] = custom_sep
            st.session_state["encoding"] = custom_enc
            try:
                df = safe_load_table(file, custom_sep, custom_enc)
            except:
                st.error("Не удалось открыть таблицу с введенными параметрами!")
                st.stop()
        try:
            st.sidebar.markdown("---")
            st.write("Выберите столбцы для отображения")
            columns = df.columns.tolist()
            selected_columns = [
                col for col in columns if st.checkbox(f"Показать {col}", value=True)
            ]
            st.sidebar.markdown("---")
        except:
            st.write("Не удалось прочитать колонки")

    st.markdown(
        "<h1><b><center>📋 Анализатор .csv файлов</center></b></h1>", unsafe_allow_html=True
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📄 Основная таблица",
            "🧮 Статистический анализ",
            "📈 Графический анализ",
            "📊 Корреляционный анализ",
            "❓ Помощь",
        ]
    )

    try:
        numerical_columns = df.select_dtypes(include=["number"]).columns.tolist()
        with tab1:
            if selected_columns:
                st.dataframe(df[selected_columns])
                info = {
                    'Количество строк': df.shape[0],
                    'Количество столбцов': df.shape[1],
                    'Типы данных': df.dtypes.to_dict(),
                    'Пропуски по столбцам': df.isnull().sum().to_dict(),
                }
                st.write('**Структура DataFrame:**')
                st.json(info, expanded=False)

        with tab2:
            if selected_columns:
                st.dataframe(df[selected_columns].describe().round(2))

        with tab3:
            col1, col2, col3, col4 = st.columns([0.4, 0.2, 0.2, 0.2])

            with col1:
                options = [
                    "Линейный график",
                    "Диаграмма рассеяния",
                    "Столбчатая диаграмма",
                    "Гистограмма",
                ]
                graph = st.radio("Выберите тип график:", options)

            with col2:

                if graph == "Линейный график" or graph == "Диаграмма рассеяния":
                    options_x = [col for col in numerical_columns if col in selected_columns]
                else:
                    options_x = selected_columns
                graph_x = st.selectbox(
                    "Выберите столбец для оси Х",
                    options_x,
                    index=0,
                )

            with col3:
                if graph == "Линейный график" or graph == "Диаграмма рассеяния":
                    options_y = [col for col in numerical_columns if col in selected_columns]
                else:
                    options_y = selected_columns
                graph_y = st.selectbox(
                    "Выберите столбец для оси Y",
                    options_y,
                    index=0,
                )

            with col4:
                options_agr = ["none", "sum", "count", "mean"]
                agr = st.selectbox(
                    "Выберите агрегирующую функцию",
                    options_agr,
                    index=0,
                )
                if graph == "Гистограмма":
                    nbins = st.slider("Количество bins:", 1, 30, 10, 1)
                    st.write("Столбец Y используется как color")
                try:
                    df_g = df[selected_columns]
                    if agr == "sum":
                        df_g = df.groupby(graph_x, as_index=False)[graph_y].sum()
                    elif agr == "count":
                        df_g = df.groupby(graph_x, as_index=False)[graph_y].count()
                    elif agr == "mean":
                        df_g = df.groupby(graph_x, as_index=False)[graph_y].mean()
                except:
                    st.error("Не удалось применить агрегацию к выбранной паре колонок")
                    st.stop()
            plot = st.button("Построить график")
            if plot:
                try:
                    if graph == "Линейный график":
                        label = f"Linear dependancy {graph_x} of {graph_y}(aggr by {agr})"
                        figure = px.line(df_g, x=graph_x, y=graph_y, title=label)
                    if graph == "Диаграмма рассеяния":
                        label = (
                            f"Scatter plot dependancy {graph_x} of {graph_y}(aggr by {agr})"
                        )
                        figure = px.scatter(df_g, x=graph_x, y=graph_y, title=label)
                    if graph == "Столбчатая диаграмма":
                        label = (
                            f"Bar chart dependancy {graph_x} of {graph_y}(aggr by {agr})"
                        )
                        figure = px.bar(df_g, x=graph_x, y=graph_y, title=label)
                    if graph == "Гистограмма":
                        label = f"Histogram of {graph_x} colored by {graph_y}"
                        figure = px.histogram(
                            df_g, x=graph_x, color=graph_y, nbins=nbins, title=label
                        )
                    plot_and_download(figure, label)
                except:
                    st.error("Не удалось построить график с заданными параметрами!")
                    st.stop()
        with tab4:
            if len(numerical_columns) < 2:
                st.warning(
                    "Для корреляционного анализа требуется минимум два числовых признака"
                )
            else:
                df_corr = df[numerical_columns]
                corr_matrix = df_corr.corr()
                figure = px.imshow(
                    corr_matrix,
                    text_auto=".2f",
                    aspect="auto",
                    title="Матрица корреляции числовых признаков",
                    color_continuous_scale="RdBu_r",
                )
                try:
                    plot_and_download(figure, "Матрица корреляции числовых признаков")
                except:
                    st.error("Не удалось построить матрицу корреляции признаков")
                    st.stop()
        with tab5:
            help = """
            В боковой панели (sidebar) доступна функция для загрузки файла. Кодировка и разделитель определяются автоматически.
            Если возникли проблемы с открытием таблицы или она оказалась некорректной, есть возможность вручную задать параметры разделителя и кодировки, нажав кнопку "Переопределить".

            Ниже будет представлен список столбцов, и их активация или деактивация будет действовать на все вкладки.
            Это удобно для исключения ненужных признаков при статистическом анализе или при выборе параметров для графиков.

            На вкладке "Основная таблица" отображается полная таблица. Управление включением и отключением колонок осуществляется через боковую панель.

           Во вкладке "Статистический анализ" представлены основные статистические показатели для числовых столбцов.
            Здесь также можно управлять активацией или деактивацией колонок через боковую панель.

            Вкладка "Графический анализ" позволяет выбрать тип графика, задать параметры для осей X и Y, а также применить группировку для столбца X и агрегирующую функцию для столбца Y, если это необходимо.
            Для упрощения выбора параметров ненужные колонки можно отключить в боковой панели. Для линейных графиков и диаграмм рассеяния доступны только числовые признаки.
            Кроме того, есть функция сохранения графика в файл.

            На вкладке "Корреляционный анализ" можно наблюдать взаимозависимость числовых параметров. Также здесь есть возможность сохранить график в файл по мере необходимости.

            """
            st.write(help)
    except:
        st.error("Ошибка чтения файла!")


if __name__ == "__main__":
    main()