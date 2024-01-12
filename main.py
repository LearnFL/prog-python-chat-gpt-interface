"""
This project was created by Dennis Rotnov. Feel free to use, reuse and modify it, but please retain this authorship attribution.

"""

import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
import nltk
from nltk.corpus import stopwords
import math
from more_itertools import batched
from better_profanity import profanity
from typing import Iterator, Optional
import re

load_dotenv()


class OpenAIAPI():

    def text_cleaner(self, prompt: str) -> str:
        """
        Cleans the text by removing stopwords to make prompt shorter and censoring profane words.

        Args:
            prompt (str): The text to be cleaned.

        Returns:
            str: The cleaned text.
        """
        english_stopwords = stopwords.words('english')
        tokenized_words = re.findall('[a-z.]+', prompt, flags=re.IGNORECASE)
        if len(tokenized_words) > 30:
            prompt = " ".join([word for word in tokenized_words if word not in english_stopwords])
            return profanity.censor(prompt)
        return profanity.censor(prompt)

    def batched_prompt(self, prompt: str, token_size: int) -> Iterator[str]:
        """
        Splits a long prompt into batches of certain length expressed in tokens.

        Args:
            prompt (str): The prompt to be split.
            token_size (int): The size of a text batch in tokens.

        Returns:
            Iterator[str]: An iterator of batches of text.
        """
        prompt = self.text_cleaner(prompt)
        prompt_array = re.findall('[a-z.]+', prompt, flags=re.IGNORECASE)
        total_tokens = math.ceil(len(prompt_array)*1.4)
        batches = math.ceil(total_tokens / token_size)
        if total_tokens > token_size:
            for batch in batched(prompt_array, math.ceil(len(prompt_array)/batches)):
                yield " ".join(batch)
        yield prompt

    async def generate_chat_response(self, prompt: str, *, model: str, api_key: Optional[str]=os.getenv('OPENAI_API_KEY')) -> str:
        """
        Generate a response from the OpenAI API based on the chat model.

        Args:
            prompt (str): The prompt to be used for generating the response.
            model (str): The model to be used for generating the response.
            api_key (Optional[str]): The API key to be used for generating the response. If not provided, the value of the OPENAI_API_KEY environment variable will be used.

        Returns:
            str: The generated response.
        """
        prompt = self.text_cleaner(prompt)
        client = AsyncOpenAI(api_key=api_key)
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
        except Exception as e:
            print(f"Error while fetching response. Error: {e}")
        else: return completion.choices[0].message.content

    async def generate_completetion_response(self, prompt: str, *, model: str, api_key: Optional[str]=os.getenv('OPENAI_API_KEY')) -> str:
        """
        Generate a completion response from the OpenAI API based on the completion model.

        Args:
            prompt (str): The prompt to be used for generating the response.
            model (str): The model to be used for generating the response.
            api_key (Optional[str]): The API key to be used for generating the response. If not provided, the value of the OPENAI_API_KEY environment variable will be used.

        Returns:
            str: The generated response.
        """
        prompt = self.text_cleaner(prompt)
        client = AsyncOpenAI(api_key=api_key)
        try:
            completions = await client.completions.create(
                model=model,
                prompt=prompt,
                n=1,
                top_p=1,
                stop=None,
                temperature=0.5,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
        except Exception as e:
            print(f"Error while fetching response. Error: {e}")
        else: return completions.choices[0].text

    async def generate_image(self, prompt: str, *, model: str, api_key: Optional[str]=os.getenv('OPENAI_API_KEY')) -> str:
        """
        Generate an image from the OpenAI API based on the image model.

        Args:
            prompt (str): The prompt to be used for generating the image.
            model (str): The model to be used for generating the image.
            api_key (Optional[str]): The API key to be used for generating the image. If not provided, the value of the OPENAI_API_KEY environment variable will be used.

        Returns:
            str: The generated image URL.
        """
        client = AsyncOpenAI(api_key=api_key)
        try:
            response = await client.images.generate(
                model=model,
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
        except Exception as e:
            print(f"Error while fetching response. Error: {e}")
        else: return image_url

     async def generate_batches(self, prompt: str, *, task: str, method: str, model: str, api_key: Optional[str]=os.getenv('OPENAI_API_KEY'), token_size: int) -> str:
        """
        Generate multiple responses in parallel using the OpenAI API.

        Args:
            prompt (str): The prompt to be used for generating the responses.
            method (str): The method to be used for generating the responses. Can be either "chat" or "completions".
            model (str): The model to be used for generating the responses.
            api_key (Optional[str]): The API key to be used for generating the responses. If not provided, the value of the OPENAI_API_KEY environment variable will be used.
            token_size (int): The size of a text batch in tokens.
            task (str): Provides instruction on what to do with each batch.

        Returns:
            str: A string containing the responses generated by the API.
        """
        batches = self.batched_prompt(prompt, token_size)
        queue = asyncio.Queue(maxsize=0)
        for batch in batches:
            match method:
                case "chat":
                    await queue.put(await self.generate_chat_response(
                        task + batch, model=model, api_key=api_key))
                case "completions":
                    await queue.put(await self.generate_completions_response(
                        task + batch, model=model, api_key=api_key))
        if not queue.empty():
            summary_array = []
            [summary_array.append(await queue.get()) for _ in range(queue.qsize())]
            return \
                await self.generate_chat_response(f'You are a professional educator and researcher, specializing in analysing and delivering informtion in a way that is easy to understand and you never miss important details like main idea, facts, cause and effect, problems and solutions. {task}: {" ".join(summary_array)}', model=model, api_key=api_key) \
                if method == "chat" \
                    else await self.generate_completetion_response(f'You are a professional educator and researcher, specializing in analysing delivering informtion in a way that is easy to understand and you never miss important details like main idea, facts, cause and effect, problems and solutions. {task}: {" ".join(summary_array)}', model=model, api_key=api_key)
        return "Something went wrong"

    @classmethod
    def generate(cls, prompt: str, *, task: Optional[str]=None, method: Optional[str]=None, api_key: Optional[str]=None, token_size: Optional[int]=None, model: Optional[str]=None, get: Optional[str]=None) -> str:
        """
        Generate a response from the OpenAI API based on the specified parameters.

        Args:
            prompt (str): The prompt to be used for generating the response.
            method (Optional[str]): The method to be used for generating the response. Can be either "chat" or "completions".
            api_key (Optional[str]): The API key to be used for generating the response. If not provided, the value of the OPENAI_API_KEY environment variable will be used.
            token_size (Optional[int]): The size of a text batch in tokens.
            model (str): The model to be used for generating the response.
            task (Optional[str]): Provides instruction for batches.
            get (str): The type of response to generate. Can be either "chat", "completions", or "image".

        Returns:
            Union[str, ValueError]: The generated response or a ValueError if the input parameters are invalid.
        """
        if get is None:
            raise ValueError("Type must be specified either 'chat or completions or image'")
        if model is None: raise ValueError("Model must be specified")

        match get:
            case "chat":
                return asyncio.run(cls().generate_chat_response(prompt, model=model, api_key=api_key))
            case "completions":
                return asyncio.run(cls().generate_completetion_response(prompt, model=model, api_key=api_key))
            case "image":
                return asyncio.run((cls().generate_image(prompt, model=model, api_key=api_key)))
            case "batches":
                return asyncio.run(cls().generate_batches(prompt, task=task, method=method, model=model, api_key=api_key ,token_size=token_size))
