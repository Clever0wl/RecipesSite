import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, render_template, jsonify
import pandas as pd
import ast

app = Flask(__name__)

# Загружаем датасет
dataframe = pd.read_csv('povarenok_recipes_cleaned.csv')
dataframe['ingredients'] = dataframe['ingredients'].apply(ast.literal_eval)

all_ingredients = set()
for recipe_ingredients in dataframe['ingredients']:
    all_ingredients.update(recipe_ingredients.keys())
all_ingredients = {ingredient.lower() for ingredient in all_ingredients}

# Функция для парсинга данных о блюде
def fetch_recipe_info(url):
    """
    Парсит страницу рецепта и возвращает данные о калориях, белках, жирах, углеводах и калориях на 100 г.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')  # Используем lxml для ускорения парсинга

        # Ищем блок с питательной ценностью
        nutrition_block = soup.find("div", itemprop="nutrition")
        if not nutrition_block:
            return {
                "calories": "N/A",
                "proteins": "N/A",
                "fats": "N/A",
                "carbs": "N/A",
                "calories100g": "N/A",
                "weight": "N/A"
            }

        # Извлекаем данные из блока
        calories = nutrition_block.find("strong", itemprop="calories")
        protein = nutrition_block.find("strong", itemprop="proteinContent")
        fat = nutrition_block.find("strong", itemprop="fatContent")
        carbs = nutrition_block.find("strong", itemprop="carbohydrateContent")

        # Извлекаем калории на 100 г
        calories_100g = "N/A"
        row_with_100g = nutrition_block.find("strong", string="100 г блюда")
        if row_with_100g:
            calories_100g_td = row_with_100g.find_parent("tr").find_next_sibling("tr").find("strong")
            calories_100g = calories_100g_td.text.strip() if calories_100g_td else "N/A"

        return {
            "calories": calories.text.strip() if calories else "N/A",
            "proteins": protein.text.strip() if protein else "N/A",
            "fats": fat.text.strip() if fat else "N/A",
            "carbs": carbs.text.strip() if carbs else "N/A",
            "calories100g": calories_100g
        }
    except Exception as e:
        print(f"Ошибка при парсинге {url}: {e}")
        return {
            "calories": "N/A",
            "proteins": "N/A",
            "fats": "N/A",
            "carbs": "N/A",
            "calories100g": "N/A"
        }



    except Exception as e:
        print(f"Ошибка при парсинге {url}: {e}")
        return {
            "calories": "N/A",
            "proteins": "N/A",
            "fats": "N/A",
            "carbs": "N/A",
            "calories100g": "N/A",
            "weight": "N/A"
        }

# Функция для параллельной загрузки данных
def fetch_recipe_info_parallel(urls):
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(fetch_recipe_info, urls))
    return results

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check-ingredient", methods=["POST"])
def check_ingredient():
    ingredient = request.json.get("ingredient", "").strip().lower()
    if ingredient in all_ingredients:
        return jsonify({"status": "found", "ingredient": ingredient})
    return jsonify({"status": "not_found", "ingredient": ingredient})

@app.route("/get-recipes", methods=["POST"])
def get_recipes():
    # Получаем список ингредиентов пользователя
    user_ingredients = request.json.get("ingredients", [])

    # Проверяем, пуст ли список ингредиентов
    if not user_ingredients:
        return jsonify({"error": "Ингредиенты не были предоставлены. Пожалуйста, добавьте хотя бы один продукт."}), 400

    # Преобразуем в нижний регистр
    user_ingredients = {ingredient.lower() for ingredient in user_ingredients}

    # Функция для подсчёта совпадений ингредиентов
    def count_matches(recipe_ingredients):
        recipe_ingredients = {ingredient.lower(): amount for ingredient, amount in recipe_ingredients.items()}
        matches = set(user_ingredients) & set(recipe_ingredients.keys())
        return len(matches)

    # Функция для проверки точного совпадения ингредиентов
    def is_exact_match(recipe_ingredients):
        recipe_ingredients = {ingredient.lower(): amount for ingredient, amount in recipe_ingredients.items()}
        if set(user_ingredients) != set(recipe_ingredients.keys()):
            return False
        return True

    # Фильтруем рецепты
    dataframe['num_ingredients'] = dataframe['ingredients'].apply(lambda x: len(x.keys()))
    dataframe['matches'] = dataframe['ingredients'].apply(count_matches)
    dataframe['exact_match'] = dataframe['ingredients'].apply(is_exact_match)
    dataframe['diference'] = dataframe['num_ingredients'] - dataframe['matches']

    sorted_recipes = dataframe.sort_values(by=['exact_match', 'matches', 'diference'], ascending=[False, False, True])
    top_recipes = sorted_recipes.head(10)

    # Получаем результаты параллельно
    recipe_urls = top_recipes['url'].tolist()
    recipe_info = fetch_recipe_info_parallel(recipe_urls)

    # Формируем результат
    response = []
    for i, row in enumerate(top_recipes.iterrows()):
        row = row[1]
        recipe_info_data = recipe_info[i]
        match_info = f"{row['matches']} из {len(row['ingredients'])} ингредиентов"
        response.append({
            'name': row['name'],
            'url': row['url'],
            'match_info': match_info,
            **recipe_info_data  # Включаем данные о калориях, БЖУ, весе
        })

    return jsonify(response)

if __name__ == "__main__":
    app.run(debug=True)
