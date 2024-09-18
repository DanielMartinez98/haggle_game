import pygame
import sys
import random
import openai
import os
import re
import requests  # For downloading images
from textblob import TextBlob
from openai import OpenAIError

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Haggling Game with ChatGPT")
font = pygame.font.SysFont(None, 32)

# Import OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")  # Ensure to set this in your environment

# Game state variables
attempt = 0
max_attempts = 3
player_turn = 1
player_prices = {1: None, 2: None}
input_text = ''
owner_response = ''
conversation_history = []
awaiting_continue = False  # New flag to wait for extra input

def generate_item():
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that provides interesting and unique store items to sell. "
                        "Output the item name and description in the following format:\n"
                        "Item Name: [name]\nDescription: [description]"
                    )
                },
                {
                    "role": "user",
                    "content": "Generate a unique item for sale in a store, including a short name and a brief description."
                }
            ],
            max_tokens=100,
            temperature=0.7
        )
        item_info = response.choices[0].message['content']
        # Parse the item_info to extract name and description
        name_match = re.search(r"Item Name:\s*(.*)", item_info)
        desc_match = re.search(r"Description:\s*(.*)", item_info)
        if name_match and desc_match:
            item_name = name_match.group(1).strip()
            item_description = desc_match.group(1).strip()
        else:
            # If parsing fails, use default values
            item_name = "Mystery Item"
            item_description = "An intriguing item with unknown properties."
        return item_name, item_description
    except OpenAIError as e:
        print(f"An error occurred while generating item: {e}")
        return "Mystery Item", "An intriguing item with unknown properties."

def generate_item_image(item_name):
    # Use OpenAI Image API to generate an image of the item
    try:
        response = openai.Image.create(
            prompt=f"A detailed, high-quality image of a {item_name}",
            n=1,
            size="256x256"
        )
        image_url = response['data'][0]['url']
        # Download the image and save it locally
        image_data = requests.get(image_url).content
        image_filename = 'item_image.png'
        with open(image_filename, 'wb') as handler:
            handler.write(image_data)
        return image_filename
    except OpenAIError as e:
        print(f"An error occurred while generating item image: {e}")
        return None

def get_store_owner_response(conversation_history, current_price):
    # Build the messages list
    messages = [
        {
            "role": "system",
            "content": (
                "You are a store owner skilled in negotiation. "
                "Decide on a counteroffer price based on the customer's plea. "
                "Include the price you are offering back in your response, and make sure it is different from any price the customer mentioned. "
                "Clearly state your counteroffer price in a format like '$X'. "
                "Do not mention any prices proposed by the customer in your response. "
                "You are sassy, a bit sarcastic, and can also choose to increase the price if you want. "
                "Be sure to keep the conversation short and sweet."
            )
        }
    ]
    # Append the conversation history
    for speaker, text in conversation_history:
        role = "user" if speaker == "Player" else "assistant"
        messages.append({"role": role, "content": text})

    # Inform the assistant of the current price
    messages.append({
        "role": "system",
        "content": f"The current price is ${current_price:.2f}. Respond accordingly."
    })

    # Call the API with error handling
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Or "gpt-4" if available
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message['content']
    except OpenAIError as e:
        print(f"An error occurred: {e}")
        return "I'm sorry, there was an error processing your request."

def extract_prices(text):
    price_pattern = r'\$?(\d+\.?\d*)'
    prices_found = re.findall(price_pattern, text.replace(',', ''))
    prices = [float(price_str) for price_str in prices_found]
    return prices

def adjust_price(player_input, owner_response, current_price):
    # Extract prices from player's input and owner's response
    player_prices_input = extract_prices(player_input)
    owner_prices = extract_prices(owner_response)

    # Filter out any owner_prices that match player_prices_input
    filtered_owner_prices = [price for price in owner_prices if price not in player_prices_input]

    # Now, select the first reasonable price from filtered_owner_prices
    new_price = current_price
    if filtered_owner_prices:
        for price in filtered_owner_prices:
            if 0 < price < current_price * 2:  # Assuming the price won't be more than double
                new_price = price
                break
    else:
        # If no valid price is found, keep the current price
        pass

    return new_price

def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ''
    for word in words:
        test_line = current_line + word + ' '
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word + ' '
    lines.append(current_line)
    return lines

def reset_game():
    global attempt, max_attempts, player_turn, player_prices
    global input_text, owner_response, conversation_history
    global store_price, original_price, awaiting_continue
    global item_name, item_description, item_image, scaled_item_image  # Add item variables
    attempt = 0
    max_attempts = 3
    player_turn = 1
    player_prices = {1: None, 2: None}
    input_text = ''
    owner_response = ''
    conversation_history = []
    awaiting_continue = False

    # Generate new item and price
    item_name, item_description = generate_item()
    original_price = random.randint(100, 500)
    store_price = original_price

    # Generate item image
    item_image_path = generate_item_image(item_name)
    if item_image_path:
        item_image = pygame.image.load(item_image_path)
        # Scale down the image to a smaller size (e.g., 128x128)
        scaled_item_image = pygame.transform.scale(item_image, (128, 128))
    else:
        scaled_item_image = None  # Or use a default image

def game_over_screen():
    # Determine winner
    if player_prices[1] < player_prices[2]:
        winner = 1
    elif player_prices[1] > player_prices[2]:
        winner = 2
    else:
        winner = None  # It's a tie

    # Game over screen loop
    while True:
        screen.fill((255, 255, 255))  # Clear screen with white background

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Check if Play Again button is clicked
                if play_again_button.collidepoint(event.pos):
                    return 'play_again'

        # Display the result
        result_text = font.render("Game Over!", True, (0, 0, 0))
        screen.blit(result_text, (350, 100))
        p1_price_text = font.render(f"Player 1's final price: ${player_prices[1]:.2f}", True, (0, 0, 0))
        screen.blit(p1_price_text, (250, 200))
        p2_price_text = font.render(f"Player 2's final price: ${player_prices[2]:.2f}", True, (0, 0, 0))
        screen.blit(p2_price_text, (250, 240))

        if winner:
            winner_text = font.render(f"Player {winner} wins!", True, (0, 0, 0))
        else:
            winner_text = font.render("It's a tie!", True, (0, 0, 0))
        screen.blit(winner_text, (350, 300))

        # Draw Play Again button
        play_again_button = pygame.Rect(340, 400, 140, 50)
        pygame.draw.rect(screen, (0, 200, 0), play_again_button)
        play_again_text = font.render("Play Again", True, (255, 255, 255))
        text_rect = play_again_text.get_rect(center=play_again_button.center)
        screen.blit(play_again_text, text_rect)

        pygame.display.flip()

# Main game loop
game_running = True
while game_running:
    reset_game()
    running = True
    while running:
        screen.fill((255, 255, 255))  # Clear screen with white background

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                game_running = False
                pygame.quit()
                sys.exit()

            # Handle text input
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if awaiting_continue:
                        # Proceed to next player's turn or end game
                        if attempt >= max_attempts:
                            if player_turn == 1:
                                # Reset for player 2
                                attempt = 0
                                store_price = original_price
                                player_turn = 2
                                conversation_history = []
                                awaiting_continue = False
                            else:
                                # End game after both players have played
                                running = False
                                awaiting_continue = False
                        else:
                            awaiting_continue = False
                    else:
                        if input_text.strip() != '':
                            # Append player's input to conversation history
                            conversation_history.append(("Player", input_text))

                            # Print player's input to console
                            print(f"Player {player_turn}: {input_text}")

                            # Send conversation history to ChatGPT
                            owner_response = get_store_owner_response(conversation_history, store_price)

                            # Append owner's response to conversation history
                            conversation_history.append(("Owner", owner_response))

                            # Print owner's response to console
                            print(f"Owner: {owner_response}")

                            # Adjust price based on owner's response
                            new_price = adjust_price(input_text, owner_response, store_price)
                            store_price = new_price

                            attempt += 1
                            input_text = ''

                            if attempt >= max_attempts:
                                player_prices[player_turn] = store_price
                                awaiting_continue = True  # Wait for extra input
                        else:
                            # Ignore empty input
                            pass
                elif event.key == pygame.K_BACKSPACE:
                    if not awaiting_continue:
                        input_text = input_text[:-1]
                else:
                    if not awaiting_continue:
                        input_text += event.unicode

        # Display item and price
        item_text = font.render(f"Item: {item_name}", True, (0, 0, 0))
        price_text = font.render(f"Price: ${store_price:.2f}", True, (0, 0, 0))
        screen.blit(item_text, (50, 20))
        screen.blit(price_text, (50, 60))

        # Display item image if available
        if scaled_item_image:
            screen.blit(scaled_item_image, (50, 100))

        # Display conversation history with text wrapping
        y_offset = 100
        if scaled_item_image:
            image_height = scaled_item_image.get_height()
            y_offset += image_height + 20  # Adjust y_offset if image is displayed
        else:
            y_offset += 20  # Add some spacing if no image

        max_width = 700  # Adjust according to screen size and margins
        line_height = font.get_linesize()
        max_lines = (500 - y_offset - 50) // line_height  # Adjust the vertical space available
        displayed_lines = []
        for speaker, text in conversation_history[-10:]:  # Limit number of messages
            wrapped_lines = wrap_text(f"{speaker}: {text}", font, max_width)
            displayed_lines.extend(wrapped_lines)

        # Only display as many lines as fit on screen
        displayed_lines = displayed_lines[-(max_lines):]

        for line in displayed_lines:
            convo_text = font.render(line, True, (0, 0, 0))
            screen.blit(convo_text, (50, y_offset))
            y_offset += line_height

        if awaiting_continue:
            # Display message to press Enter to continue
            continue_text = font.render("Press Enter to continue...", True, (0, 0, 0))
            screen.blit(continue_text, (300, 550))
        else:
            # Display input box
            input_box = pygame.Rect(50, 500, 700, 32)
            pygame.draw.rect(screen, (200, 200, 200), input_box)

            # Render the input text
            text_surface = font.render(input_text, True, (0, 0, 0))
            # If the text is wider than the input box, adjust the x-coordinate
            if text_surface.get_width() > input_box.width - 10:
                offset = text_surface.get_width() - (input_box.width - 10)
            else:
                offset = 0
            screen.blit(text_surface, (input_box.x + 5 - offset, input_box.y + 5))

            # Display attempts
            attempts_text = font.render(f"Attempt: {attempt + 1}/{max_attempts}", True, (0, 0, 0))
            screen.blit(attempts_text, (50, 550))

        # Display player turn, moved closer to center
        player_text = font.render(f"Player {player_turn}'s Turn", True, (0, 0, 0))
        text_rect = player_text.get_rect()
        text_rect.topright = (750, 20)  # Adjusted position
        screen.blit(player_text, text_rect)

        pygame.display.flip()

    # After main game loop ends, display game over screen
    player_choice = game_over_screen()
    if player_choice == 'play_again':
        continue  # Start a new game
    else:
        game_running = False  # Exit outer loop
        pygame.quit()
        sys.exit()
