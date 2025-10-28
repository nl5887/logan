import asyncio
import httpx
from bs4 import BeautifulSoup
import polars as pl


@mitre_cache_loader(cache_key="mitre-tactics", ttl=604800)
async def get_mitre_tactic_info(self):
    url = "https://attack.mitre.org/tactics/enterprise/"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    head = table.find("thead")
    col_names = [item.text for item in head.find_all("th")]
    body = table.find("tbody")
    data = []
    for row in body.find_all("tr"):
        data.append(
            {
                key: value
                for key, value in zip(
                    col_names, [item.text.strip() for item in row.find_all("td")]
                )
            }
        )

    df = pl.DataFrame(data)
    return df


async def _process_tactic(client: httpx.AsyncClient, tactic: str):
    """Process a single tactic and return its DataFrame."""
    url = f"https://attack.mitre.org/tactics/{tactic}/"
    resp = await client.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    head = table.find("thead")
    col_names = [item.text for item in head.find_all("td")]
    body = table.find("tbody")
    data = []
    technique = None

    for row in body.find_all("tr"):
        if row.attrs.get("class") == ["technique"]:
            row_data = [item.text.strip() for item in row.find_all("td")]
            technique = row_data[0]
        elif row.attrs.get("class") == ["sub", "technique"]:
            row_data = [item.text.strip() for item in row.find_all("td")[1:]]
            row_data[0] = technique + row_data[0]

        data.append({key: value for key, value in zip(col_names, row_data)})

    df_tactic = pl.DataFrame(data)
    df_tactic = df_tactic.with_columns(
        hyperlink=pl.lit("https://attack.mitre.org/techniques/")
        + pl.col("ID").str.replace(".", "/", literal=True),
        TacticId=pl.lit(tactic),
    )[["TacticId", "ID", "Name", "Description", "hyperlink"]]

    return df_tactic


@mitre_cache_loader(cache_key="mitre-techniques", ttl=604800)
async def get_mitre_technique_info(self):
    df = await self.get_mitre_tactic_info()

    async with httpx.AsyncClient() as client:
        # Create tasks for all tactics to run in parallel
        tasks = [_process_tactic(client, tactic) for tactic in df["ID"]]

        # Execute all tasks concurrently
        dfs_tactic = await asyncio.gather(*tasks)

    df = pl.concat(dfs_tactic)
    return df
