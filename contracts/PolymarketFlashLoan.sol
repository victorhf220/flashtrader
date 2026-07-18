// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

// Aave V3 Interfaces
interface IPoolAddressesProvider {
    function getPool() external view returns (address);
}

interface IPool {
    function flashLoanSimple(
        address receiverAddress,
        address token,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

interface IFlashLoanSimpleReceiver {
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool);
}

/**
 * @title PolymarketFlashLoan
 * @dev Flash loan orchestrator para Polymarket arbitrage
 * 
 * FLUXO:
 * 1. Bot Python chama requestFlashLoan(amount)
 * 2. Contrato pega USDC da Aave V3
 * 3. executeOperation() é chamado automaticamente pela Aave
 * 4. Contrato transfere USDC pra wallet Python
 * 5. Emite evento "FlashLoanExecuted" que Python ouve
 * 6. Python arbitra na Polymarket com USDC emprestado
 * 7. Python aguarda settlement na Polymarket
 * 8. Python envia transação de repagamento (repayFlashLoan)
 * 9. Contrato repaga Aave + extrai lucro pro owner
 */
contract PolymarketFlashLoan is IFlashLoanSimpleReceiver, ReentrancyGuard, Ownable {
    IPool public immutable AAVE_POOL;
    IERC20 public immutable USDC;
    
    address public pyBotWallet;  // Carteira que o Python controla
    uint256 public lastFlashLoanAmount;
    uint256 public lastFlashLoanPremium;
    
    event FlashLoanRequested(uint256 amount, address indexed requester);
    event FlashLoanExecuted(uint256 amount, uint256 premium, address indexed pyBot);
    event FlashLoanRepaid(uint256 amount, uint256 premium, uint256 profit);
    event ProfitWithdrawn(uint256 amount);
    
    modifier onlyPyBot() {
        require(msg.sender == pyBotWallet, "Only Python bot allowed");
        _;
    }
    
    constructor(address _pyBotWallet) {
        // Aave Pool Addresses Provider na Polygon
        IPoolAddressesProvider provider = IPoolAddressesProvider(
            0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
        );
        AAVE_POOL = IPool(provider.getPool());
        
        // USDC na Polygon
        USDC = IERC20(0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174);
        
        pyBotWallet = _pyBotWallet;
    }
    
    /**
     * @dev Solicita flash loan (chamado pelo bot Python)
     * @param amount Quantidade de USDC a emprestar
     */
    function requestFlashLoan(uint256 amount) external onlyOwner {
        require(amount > 0, "Amount must be > 0");
        
        emit FlashLoanRequested(amount, msg.sender);
        
        // Pede flash loan da Aave
        AAVE_POOL.flashLoanSimple(
            address(this),
            address(USDC),
            amount,
            abi.encode(amount),  // Params: passa o amount original
            0  // referralCode
        );
    }
    
    /**
     * @dev Callback da Aave (chamado automaticamente)
     * Transfere USDC pro bot Python fazer arbitrage
     */
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        require(msg.sender == address(AAVE_POOL), "Only Aave can call");
        require(asset == address(USDC), "Only USDC supported");
        
        // Guarda os valores (usado depois no repay)
        lastFlashLoanAmount = amount;
        lastFlashLoanPremium = premium;
        
        // Transfere USDC pro bot Python
        require(USDC.transfer(pyBotWallet, amount), "Transfer failed");
        
        emit FlashLoanExecuted(amount, premium, pyBotWallet);
        
        // Aprova Aave para pegar o dinheiro de volta no repay
        // (Python vai devolver, e a gente autoriza Aave pegar)
        require(
            USDC.approve(address(AAVE_POOL), amount + premium),
            "Approval failed"
        );
        
        // Retorna true = sucesso (senão Aave reverte)
        return true;
    }
    
    /**
     * @dev Repaga o flash loan (chamado pelo bot Python após arbitrage)
     * 
     * Fluxo:
     * 1. Python recebe USDC emprestado
     * 2. Python arbitra na Polymarket
     * 3. Python ganha lucro
     * 4. Python transfere (USDC emprestado + premium + lucro) pra cá
     * 5. Chama repayFlashLoan
     * 6. A gente repaga Aave
     * 7. O resto (lucro) fica com o owner
     */
    function repayFlashLoan() external onlyPyBot nonReentrant {
        uint256 totalOwed = lastFlashLoanAmount + lastFlashLoanPremium;
        
        // Verifica que Python devolveu o dinheiro
        uint256 balance = USDC.balanceOf(address(this));
        require(balance >= totalOwed, "Insufficient USDC for repayment");
        
        // Repaga Aave
        require(
            USDC.transfer(address(AAVE_POOL), totalOwed),
            "Repayment failed"
        );
        
        // O que sobrou é lucro
        uint256 profit = balance - totalOwed;
        
        emit FlashLoanRepaid(lastFlashLoanAmount, lastFlashLoanPremium, profit);
        
        // Limpa
        lastFlashLoanAmount = 0;
        lastFlashLoanPremium = 0;
    }
    
    /**
     * @dev Owner retira o lucro
     */
    function withdrawProfit() external onlyOwner {
        uint256 balance = USDC.balanceOf(address(this));
        require(balance > 0, "No profit to withdraw");
        
        require(USDC.transfer(owner(), balance), "Withdrawal failed");
        
        emit ProfitWithdrawn(balance);
    }
    
    /**
     * @dev Muda a carteira do bot Python
     */
    function setPyBotWallet(address newWallet) external onlyOwner {
        require(newWallet != address(0), "Invalid address");
        pyBotWallet = newWallet;
    }
    
    /**
     * @dev Emergência: retira qualquer token preso
     */
    function emergencyWithdraw(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No balance");
        IERC20(token).transfer(owner(), balance);
    }
}
