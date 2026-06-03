from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "connection_logs" ADD "response_body" TEXT;
        ALTER TABLE "connection_logs" ADD "request_body" TEXT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "connection_logs" DROP COLUMN "response_body";
        ALTER TABLE "connection_logs" DROP COLUMN "request_body";"""


MODELS_STATE = (
    "eJztXWtv2zgW/SuEP3WAbDZ208cWiwWcNJ3xNi80ye5gJgMNLTE2EYnUiFQSo+h/H5KWrB"
    "elmLYVS46+OA7JI1GHV9S9h5fy955HHeSy/eEEEXvW+wS+9wj0kPiSq9kDPej7Sbks4HDs"
    "qqZQtsFIFcIx4wG0uSi/gy5DoshBzA6wzzElsvXP9AEFxEOEAwWcAXXIfYl2qC3gmEyqGt"
    "6SMxwENGCATxH4Mz77n0B1CNwF1FM1NMATTKALrkIfjiFDgNlT5EF1ppDgv0JkcTpBom0g"
    "zvf7H6IYEwc9iSuJ/vXvrTuMXCfDDHbkAVS5xWe+Kru5GX3+olrKqxhbNnVDjySt/RmfUr"
    "JoHobY2ZcYWSf6jwLIkZPijISuG9EbF817LAp4EKJFV52kwEF3MHQl871/34XEloQDMWr7"
    "IcdiJOPTWPLk/+kVBkaeMjcEUZFNiRxUTLgk5vuP+SUmBKjSnjzv8S/Db2/evv9JXTJlfB"
    "KoSkVP74cCQg7nUEVywqr6W+D1eAoDPa9x+xyzoqOrcBoXJKQm1huzGhO0Gms9Dz5ZLiIT"
    "PhX/Dt69q6Dxf8NviknRSlFJxR01v9XOo6rBvE5SmlDIpjTglimRWdRKdEYGuDU23x0sQe"
    "a7g1IuZVWWSpdOqAmJcftW0jdYhr5BOX2DAn3pbhVYvEZPXM9iDtYSMivIuz759Vr22WPs"
    "LzdN2puz4a+KT28W1ZxenP8cN0+RfHx6cZQjV5yeIDW7z6nRmukJCT1F8kj0FRIbFcjWHO"
    "bl5tLe8HJUfAT1zo4vPwHxcUtE/ScgPsS3wVB8Gwzz/sEylt1fxrL75ZbdL1i2IJOHbFXO"
    "E/QLUi28MfyANGzPKz6B+d9bIpylqCT+tgrnNcwm0mdgNtXZ+n+vLs5LJpMMKsf3DREc/O"
    "5gm+8BFzP+R23sJ67YOMQux4TtyxPW5IBJOqonnPzckvPU5AGKE45LA5On4QLQkhm8bm8C"
    "Ecen4mRWGLgmPOZxraSzf3Cw3Cx8UDUPHxRIhSGfWp6I3qgmHivnNAdrJaWbt1DFyhRBBx"
    "nd6DlYK8nsL2ueVdaZ51PKDZYPxQkM2MyAWsllLWEt9LF1j2bGgW0e10pGa7FOJQO52MPc"
    "CnyvyOmIlARoRWCOVHERzSR1Is/zj0H/8MPhx7fvDz+KJqori5IPFTSPzq/zDCLRc8atOx"
    "p4kJtYZRHZSrus4REkbtfY4dEEWOWOfgHY+fqr+/qiyhc9QNZcKzcZBw20G4nVR0KaNfOR"
    "bQXw0UREy+NaMr28tIqGngRH4vqFwzVzKdTEEOWWrsNuwNQbRXptNj0PF4xn+BRsS1Tvwq"
    "TCKYeuZUPX1QxAqduXQ63k8600jx80yOODYsAnVuibucsJ5jWz5tBHzULQc7zFqFfJnB0g"
    "eXGWLrr4LGo49lCJ+ppB5shzIuh+/KUuKtcMNsQ1OBfEnUVzdZV3MDo7uboenl1mJsvPw+"
    "sTWTPIuAdx6Zv3uQl0cRDw/9H1L0D+C367OD/Jz6mLdte/9WSfYMipReijBZ1UJkZcGhOT"
    "GdjQd1Yc2CyyG9itDqzqvMwRurtP5bPIgjG07x9h4FiZGu36rUsnmufwUXSAL1+/IReWrI"
    "ZH+VnHi4Od0kmTfcykNE0eHdAy9opV3sDLl0ACJ6rX8tzyTFpaNHltBd7K09s04/Vslls5"
    "O13iWR3O8hqJZ9DWp6lUCMt2yT1Z5yo+R4yvwV3d6t1SSSllq8VbTERpdh5VVbZJSTbfFj"
    "JMms2heILK5GHLM4l4s6BXGYA4iEOsSVeoSt+LES84L9bzPKknca8L6XbB8y+GdPGa3pg6"
    "M5MbJo97Mam+TXfNYlnJnN0csKNXQ+98a41lFltkQGuEGI1a8XgmhijE+nkOiwR+oQHCE/"
    "IVzQppwfpoPtlt1VTiCmH8npRrHxfRatY0xBWK60J87rQOr46Hn096P8pFkpolgQcUMBhd"
    "uE4RSOr3nhEEFi2X3PQmHHYO0jhwGw4O+ofAS29lyxzYbD9bZudc7WfrRIyGiRgcc9co6F"
    "4AXtBVvw0P0ADKz/6/1OeH5Pvbgfw8fKvajNVnX5V83KDosZzqUSV7FKJLP0APGBklaKQg"
    "XW5GuU8SbSheOkcghenSjlbPEGiH5NRjoW0jxjY2OWxed/JE94RRCqJCogn4S6WnAu5Vqk"
    "+L4C0WNJbPr80BWzLH1r4H6YmjQPhzFhP2JbV2nSNWsRVJD28lubXk1Hfi3o6Ke12+xk4M"
    "bNT51LgyFBjKXilIJ3pJMjYged1Eh2kqac8KXimjyMhdVyfX4Pzm9LRK7yp4i2tmA53Nj9"
    "LMqWQriUAxIxrBL0VWudaXHpfnZb4RcfADdkLoAltqcBEaPGI+xQTAjChX1O3M4Z0Q1zAh"
    "LqBmOlzcvsvWWOQRcaSLl8v1tBSkLSxuQ1DjFuPIN9bUUrBOVltDVqNhYJspmilIx/waO1"
    "rVZhKjOXmBaKm8semXXt0h5Eh3zOJiEjaZmgvAlhC6tRwXvdpZvlHqGbHztbyOwRYXN6GB"
    "JgWjIu04hWmJWdb+CoY4d8N85W2B6jbnrvykQio5w4T6BNHRvvrr7TrlfhcE3k6539GBLS"
    "j3aRXMUMHXQDepaTVZyu/WPja39mHnckXXXAPJp5421uyeXQzR3F/6HOC8NXYrSeutJNW5"
    "hqKI1SygxISXr57IK1py6WToeJj8UwIAtFXuE7ijgUpFHo6AzGgeUw4uacCh5rdCjNC35B"
    "Iy9kgDhwEYIMC4MDUHQAbGdjDzOZhCNkUsTpomSJg08F05cuiJd+suTVx3QZ52s2JFQpO3"
    "0b2Kz7O60XWXOt6z6mAmjNz8Pat5XCvFlFoYVfOIfEvcfLYxIVUDbcvi1gtk3Td/lXXh1D"
    "R0nRU+iJk0MH0hfRbVyhu9FnvEzEp+MCOXvkOF7UFS8nRP43J0jgWwLutcPJw2/QQ/urg4"
    "zYgIR6P88sfN2dHJtzd9Ra9ohOc+rjYDHHHhYd0jo5ez5GCttNFaHkYpYiz05ONAtxpdLY"
    "uVHGID+lijdIEmyWHxZVcKnZ2CvRNCZ6dg7+jArvWuwOxW89Vzgw1FxubIZLpddS+WJ91Q"
    "GqLfNlmTBingDS9HX9Eyr5xokOpca8Z4ipQSzTOhrFr5tNKjtIQCejkCsrVSLpVyCjiVcq"
    "Yw1rySKdpqRFDDA9ySE2hPJQRgBiBj1MZy/FW+OYBgLqcSR+qhAHMG6CMBPgo8rLYAMlWn"
    "/MAuIb2xwmj3u8prR073yCixLGre6cpddLJLTqwmOtlWFkGr8i4as4WyQQ7c3pIr31t+Zd"
    "gQBdie6tzAqKbSBYRJm8a8Lrw0k1x7T2rSx6PR2+ojayPJ4+Uek4ySDd8InoJ0flMqSNX8"
    "WE7V73XqfienJQTW806Rss2Q5Rnh5ZshX2zTWG0P2o1lfxtIcZt/vPz4Gw0fUvQ="
)
