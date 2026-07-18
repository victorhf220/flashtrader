// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

import {IFlashLoanSimpleReceiver} from "@aave/core-v3/contracts/flashloan/interfaces/IFlashLoanSimpleReceiver.sol";
import {IPoolAddressesProvider} from "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import {IPool} from "@aave/core-v3/contracts/interfaces/IPool.sol";
import {IERC20} from "@aave/core-v3/contracts/dependencies/openzeppelin/contracts/IERC20.sol";

/// Interface real e mínima de um router estilo Uniswap V2 (QuickSwap, SushiSwap
/// na Polygon usam essa mesma interface — são forks do Uniswap V2). Estas duas
/// funções realmente existem nos contratos deployados; ao contrário do
/// ICTFExchange usado no FlashTrader.sol original, isso NÃO é fictício.
interface IUniswapV2Router {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);
}

/// @title DexArbitrage
/// @notice Arbitragem atômica entre dois DEXs estilo Uniswap V2 na Polygon
/// (ex: QuickSwap vs SushiSwap), financiada por flash loan da Aave V3.
/// Diferente do FlashTrader.sol original (voltado à Polymarket), este
/// contrato interage apenas com funções que realmente existem on-chain:
/// swaps em AMMs são atômicos e determinísticos por natureza, então o
/// padrão flash-loan-arbitrage se encaixa aqui sem a limitação documentada
/// em POLYMARKET_ONCHAIN_LIMITACAO.md.
contract DexArbitrage is IFlashLoanSimpleReceiver {
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    IPool public immutable POOL;
    address public immutable OWNER;

    uint256 public lastProfit;
    uint256 public totalOperations;
    uint256 public totalProfit;

    event ArbitrageExecuted(
        address indexed tokenBorrowed,
        uint256 flashAmount,
        uint256 profit,
        address routerBuy,
        address routerSell
    );
    event ProfitWithdrawn(address indexed owner, address indexed token, uint256 amount);

    /// @param tokenBorrowed Token pego emprestado via flash loan (ex: USDC)
    /// @param tokenIntermediate Token intermediário do ciclo (ex: WPOL/WMATIC)
    /// @param routerBuy Router onde compramos tokenIntermediate mais barato
    /// @param routerSell Router onde vendemos tokenIntermediate mais caro
    /// @param minProfit Lucro mínimo aceito em unidades de tokenBorrowed (proteção)
    /// @param amountOutMinBuy Proteção de slippage na primeira perna (compra)
    /// @param amountOutMinSell Proteção de slippage na segunda perna (venda)
    struct ArbitrageParams {
        address tokenBorrowed;
        address tokenIntermediate;
        address routerBuy;
        address routerSell;
        uint256 minProfit;
        uint256 amountOutMinBuy;
        uint256 amountOutMinSell;
    }

    modifier onlyOwner() {
        require(msg.sender == OWNER, "Only owner");
        _;
    }

    modifier onlyPool() {
        require(msg.sender == address(POOL), "Only Aave Pool");
        _;
    }

    constructor(address provider) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(provider);
        POOL = IPool(IPoolAddressesProvider(provider).getPool());
        OWNER = msg.sender;
    }

    /// @notice Dispara o flash loan e a arbitragem. Chamado pelo bot off-chain
    /// depois de detectar spread lucrativo entre routerBuy e routerSell.
    function executeArbitrage(
        uint256 flashAmount,
        ArbitrageParams calldata params
    ) external onlyOwner {
        require(flashAmount > 0, "Invalid flash amount");
        require(params.routerBuy != params.routerSell, "Routers devem ser diferentes");

        POOL.flashLoanSimple(
            address(this),
            params.tokenBorrowed,
            flashAmount,
            abi.encode(params),
            0
        );
    }

    /// @notice Callback da Aave após o empréstimo ser transferido para este contrato.
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata data
    ) external override onlyPool returns (bool) {
        require(initiator == address(this), "Invalid initiator");

        ArbitrageParams memory params = abi.decode(data, (ArbitrageParams));
        require(asset == params.tokenBorrowed, "Asset mismatch");

        uint256 amountOwed = amount + premium;

        // Perna 1: compra tokenIntermediate no router mais barato
        uint256 intermediateReceived = _swap(
            params.routerBuy,
            asset,
            params.tokenIntermediate,
            amount,
            params.amountOutMinBuy
        );

        // Perna 2: vende tokenIntermediate de volta pro asset original no router mais caro
        uint256 finalReceived = _swap(
            params.routerSell,
            params.tokenIntermediate,
            asset,
            intermediateReceived,
            params.amountOutMinSell
        );

        require(finalReceived >= amountOwed, "Sem lucro suficiente para pagar o emprestimo");
        uint256 profit = finalReceived - amountOwed;
        require(profit >= params.minProfit, "Lucro abaixo do minimo exigido");

        lastProfit = profit;
        totalProfit += profit;
        totalOperations++;

        // Aprova a Aave a puxar de volta o valor emprestado + premium
        IERC20(asset).approve(address(POOL), amountOwed);

        emit ArbitrageExecuted(asset, amount, profit, params.routerBuy, params.routerSell);

        return true;
    }

    function _swap(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 amountOutMin
    ) internal returns (uint256) {
        IERC20(tokenIn).approve(router, amountIn);

        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        uint256[] memory amounts = IUniswapV2Router(router).swapExactTokensForTokens(
            amountIn,
            amountOutMin,
            path,
            address(this),
            block.timestamp + 300 // deadline de 5 minutos
        );

        return amounts[amounts.length - 1];
    }

    /// @notice Retira o token especificado (lucro acumulado) para o owner.
    function withdrawProfit(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "Sem saldo para retirar");
        IERC20(token).transfer(OWNER, balance);
        emit ProfitWithdrawn(OWNER, token, balance);
    }

    function emergencyWithdraw(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) {
            IERC20(token).transfer(OWNER, balance);
        }
    }

    function getStats() external view returns (
        uint256 operations,
        uint256 totalProfitAccumulated,
        uint256 lastProfitAmount
    ) {
        return (totalOperations, totalProfit, lastProfit);
    }

    receive() external payable {}
}
