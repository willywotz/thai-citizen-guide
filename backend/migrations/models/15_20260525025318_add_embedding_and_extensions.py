from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        ALTER TABLE "messages" ADD "embedding" VARCHAR(50000);
        CREATE INDEX IF NOT EXISTS idx_messages_role_created ON "messages" (role, created_at) WHERE role = 'user';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "messages" DROP COLUMN "embedding";"""


MODELS_STATE = (
    "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"
    "Oja6+FS/MhQYyl4pSCd6STI2IHndRIdpKmnPCl4po8jIXVcn1+D85vS0Su8qeItrZgOdzY"
    "/SzKFkK4lAMSMawS9FVrnWl+6X52W+EXHwA3ZC6AJbanARGjxiPsUEwIwoV9TtzOGdENcw"
    "Ic6HASLccF7JgF7JzJIJ9qiZeBm371JcFslXHOlEhnIRMgVpC4vbUCG5xTjyjYXIFKzTIt"
    "fQImkY2GYycArSMb/GNmC1A8doTF4gWqoJLSUJGbwp7A4hR/qwFheDsMnQXAC2hNCtJQbp"
    "JeLy3WXPKMSv5R0Wtri5CQ00eSsVudopTEvMsvb3VsQJL+bLlQtUt6N55ZkKqYwWE+oTRE"
    "f76rR7Y+Q4hj5CBtTS4WO5t9mpdlV5JN0C0o6uM3QLSDvasYUFpLQYayj4aaCblFbbovt1"
    "S3BLEFaxBGfnUpbXXIrLZ0A31uyeXZPTPF/6VPS8NXYLmustaNa5lKeI1azjxYSXL+LJO1"
    "pyBW/oeJj8UwIAtFUKHrijgcqIH46ATKwfUw4uacCh5idrjNC35BIy9kgDhwEYIMC4MDUH"
    "QAbGdjDzOZhCNkUszt0nSJg08F3Zc+iJd8t/TVz+Q552z2xVSLTRLbPPs7rRlaw6XvfrYC"
    "aM3Px1v3lcK+PLWhhV44h8WeF8tDEhVQNty3LhC2z+aP669cKpaejKNXwQI2lg+rsIWVQr"
    "H/Ra7BEzK/ndllwWGRW2B0nJ7J7G5egcC2Bd1rmYnDY9gx9dXJxmRISjUX5B6ebs6OTbm7"
    "6iVzTCcx9XuxEBceFh3SOjdwTlYK200VomoxQxFnrycaBb36+WxUoOsQF9rFG6QJPksPi2"
    "K4XOTsHeCaGzU7B3tGPXemVl9o0Hq6eoG4qMzZHJdJs7Xyxdv6E0RD+xsyYNUsAbXo6+om"
    "XefNIg1bnWjQspUko0z4SyauXTSvfSEgro5QjI1kq5VMop4FTKmcJY80qmaKsRQQ0PcEtO"
    "oD2VEIAZgIxRG8v+V9seAARzOZU4Ug8FmDNAHwnwUeBhtROVqTrlB3b7IhorjHY/77125H"
    "SPjFL1ouadrtxFJ7vkxGqik21lEbQq76IxO3kb5MDtLbnyveU31w1RgO2pzg2MaipdQJi0"
    "acxb60tz87XPpCYhP+q9rU5ZG0nHL/eYZJRs+GL6FKTzm1JBquY3m6p+Nlb3c00tIbCeV9"
    "uUbS8tz7Ev3176YtvwaptoN5ZPbyDFbX56+fE3/UIhYQ=="
)
