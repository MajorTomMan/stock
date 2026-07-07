import { stocks } from "stock-api";


const results = await stocks.auto.searchStocks(
    "深科技"
);


console.log(results);