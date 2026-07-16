// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

import {IFlashLoanSimpleReceiver} from "@aave/core-v3/contracts/flashloan/interfaces/IFlashLoanSimpleReceiver.sol";
import {IPoolAddressesProvider} from "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import {IPool} from "@aave/core-v3/contracts/interfaces/IPool.sol";
import {IERC20} from "@aave/core-v3/contracts/dependencies/openzeppelin/contracts/IERC20.sol";

interface ICTFExchange {
    function buyShares(
        address market,
        uint256 outcomeIndex,
        uint256 minShares,
        uint256 maxCost
    ) external returns (uint256);
    
    function sellShares(
        address market,
        uint256 outcomeIndex,
        uint256 sharesToSell,
        uint256 minProceeds
    ) external returns (uint256);
    
    function getBalance(
        address market,
        uint256 outcomeIndex,
        address account
    ) external view returns (uint256);
}

contract FlashTrader is IFlashLoanSimpleReceiver {
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    IPool public immutable POOL;
    address public immutable OWNER;
    
    IERC20 public constant USDC = IERC20(0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174); // Polygon USDC
    address public constant AAVE_POOL = 0x794a61a3DcA442b1A4B8bE2A6dff2f3dFb8C8b1; // Polygon Aave V3
    
    uint256 public lastProfit;
    uint256 public totalOperations;
    uint256 public totalProfit;
    
    event FlashLoanInitiated(address indexed token, uint256 amount);
    event ArbitrageExecuted(
        address indexed market,
        uint256 outcome,
        uint256 flashAmount,
        uint256 profit,
        bool success
    );
    event ProfitWithdrawn(address indexed owner, uint256 amount);
    
    struct ArbitrageData {
        address market;
        uint256 outcome;
        uint256 minProfit;
        uint256 minShares;      // ← NOVO: Proteção contra slippage na compra
        uint256 minProceeds;    // ← NOVO: Proteção contra slippage na venda
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
    
    function executeArbitrage(
        address market,
        uint256 outcome,
        uint256 flashAmount,
        uint256 minProfit,
        uint256 minShares,      // ← NOVO: Mínimo de shares a comprar
        uint256 minProceeds     // ← NOVO: Mínimo de USDC ao vender
    ) external onlyOwner {
        require(flashAmount > 0, "Invalid flash amount");
        require(minShares > 0, "Invalid minShares");
        require(minProceeds > 0, "Invalid minProceeds");
        
        bytes memory params = abi.encode(
            ArbitrageData({
                market: market,
                outcome: outcome,
                minProfit: minProfit,
                minShares: minShares,
                minProceeds: minProceeds
            })
        );
        
        POOL.flashLoanSimple(
            address(this),
            address(USDC),
            flashAmount,
            params,
            0
        );
    }
    
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override onlyPool returns (bytes32) {
        require(asset == address(USDC), "Invalid token");
        require(initiator == address(this), "Invalid initiator");
        
        ArbitrageData memory data = abi.decode(params, (ArbitrageData));
        
        uint256 amountOwed = amount + premium;
        bool success = false;
        uint256 profit = 0;
        
        try this._executeArbitrageLogic(data.market, data.outcome, amount, data.minShares, data.minProceeds) returns (uint256 proceeds) {
            if (proceeds > amountOwed) {
                profit = proceeds - amountOwed;
                lastProfit = profit;
                totalProfit += profit;
                success = true;
            }
        } catch {
            success = false;
        }
        
        require(success && profit >= data.minProfit, "Arbitrage not profitable");
        
        USDC.approve(address(POOL), amountOwed);
        
        totalOperations++;
        emit ArbitrageExecuted(data.market, data.outcome, amount, profit, success);
        
        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }
    
    function _executeArbitrageLogic(
        address market,
        uint256 outcome,
        uint256 amount,
        uint256 minShares,
        uint256 minProceeds
    ) external returns (uint256) {
        ICTFExchange exchange = ICTFExchange(market);
        
        // Compra shares com o flash loan (com proteção de slippage)
        uint256 sharesReceived = exchange.buyShares(
            market,
            outcome,
            minShares,  // ← AGORA: Rejeita se receber menos shares que o esperado
            amount
        );
        
        require(sharesReceived >= minShares, "Slippage too high on buy");
        require(sharesReceived > 0, "Failed to buy shares");
        
        // Vende as shares imediatamente (arbitrage, com proteção de slippage)
        uint256 proceeds = exchange.sellShares(
            market,
            outcome,
            sharesReceived,
            minProceeds  // ← AGORA: Rejeita se receber menos USDC que o esperado
        );
        
        require(proceeds >= minProceeds, "Slippage too high on sell");
        require(proceeds > 0, "Failed to sell shares");
        
        return proceeds;
    }
    
    function withdrawProfit() external onlyOwner {
        uint256 balance = USDC.balanceOf(address(this));
        require(balance > 0, "No profit to withdraw");
        
        USDC.transfer(OWNER, balance);
        emit ProfitWithdrawn(OWNER, balance);
    }
    
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = USDC.balanceOf(address(this));
        if (balance > 0) {
            USDC.transfer(OWNER, balance);
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
