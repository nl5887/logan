#!/usr/bin/env python3
"""
Test script to verify function signature extraction from tree-sitter analysis.
This file contains various function types to test signature parsing.
"""

import asyncio
from typing import List, Dict, Optional, Union
from dataclasses import dataclass


# Simple function
def simple_function():
    """Simple function with no parameters"""
    pass


# Function with basic parameters
def function_with_params(name: str, age: int):
    """Function with typed parameters"""
    return f"{name} is {age} years old"


# Function with default values
def function_with_defaults(name: str, age: int = 25, city: str = "Unknown"):
    """Function with default parameter values"""
    return f"{name}, {age}, {city}"


# Function with *args and **kwargs
def function_with_variadic(name: str, *args, **kwargs):
    """Function with variadic arguments"""
    return name, args, kwargs


# Async function
async def async_function(data: List[str]) -> Dict[str, int]:
    """Async function with complex type hints"""
    await asyncio.sleep(0.1)
    return {item: len(item) for item in data}


# Function with complex nested types
def complex_function(
    items: List[Dict[str, Union[str, int]]],
    callback: Optional[callable] = None,
    timeout: float = 30.0,
) -> Optional[Dict[str, List[str]]]:
    """Function with complex nested type annotations"""
    if callback:
        return callback(items)
    return None


class TestClass:
    """Test class to verify method signature extraction"""

    def __init__(self, name: str):
        """Constructor with parameter"""
        self.name = name

    def instance_method(self, value: int) -> str:
        """Instance method"""
        return f"{self.name}: {value}"

    @staticmethod
    def static_method(x: float, y: float) -> float:
        """Static method"""
        return x + y

    @classmethod
    def class_method(cls, data: Dict[str, any]):
        """Class method"""
        return cls("from_dict")

    async def async_method(self, items: List[str]) -> None:
        """Async instance method"""
        for item in items:
            await asyncio.sleep(0.01)
            print(item)

    def method_with_long_params(
        self,
        first_param: str,
        second_param: List[Dict[str, Union[str, int]]],
        third_param: Optional[callable] = None,
        **additional_options,
    ) -> Dict[str, any]:
        """Method with long parameter list spanning multiple lines"""
        return {
            "first": first_param,
            "second": second_param,
            "third": third_param,
            "options": additional_options,
        }


# Nested function
def outer_function(x: int):
    """Outer function containing nested function"""

    def inner_function(y: str) -> str:
        """Nested function"""
        return f"{x}: {y}"

    return inner_function


# Lambda assigned to variable (edge case)
lambda_function = lambda a, b=10: a + b


# Function with decorators
@dataclass
def decorated_function(input_data: str) -> bool:
    """Function with decorator"""
    return len(input_data) > 0


if __name__ == "__main__":
    print("Test signatures file created successfully!")
    print("This file contains various function types for signature extraction testing.")
