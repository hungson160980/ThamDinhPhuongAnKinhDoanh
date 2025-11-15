"""
Module tính toán các chỉ tiêu tài chính
"""
import math
from typing import Dict, Any, List


class FinancialCalculator:
    """Class tính toán các chỉ tiêu tài chính"""
    
    @staticmethod
    def format_number(number: float) -> str:
        """
        Format số với dấu phân cách hàng nghìn
        
        Args:
            number: Số cần format
        
        Returns:
            Chuỗi số đã format
        """
        return f"{number:,.0f}".replace(',', '.')
    
    @staticmethod
    def calculate_monthly_payment(
        principal: float,
        annual_rate: float,
        term_months: int
    ) -> float:
        """
        Tính nghĩa vụ trả nợ hàng tháng (gốc + lãi)
        
        Args:
            principal: Số tiền vay
            annual_rate: Lãi suất năm (%)
            term_months: Thời gian vay (tháng)
        
        Returns:
            Số tiền phải trả mỗi tháng
        """
        if principal <= 0 or term_months <= 0:
            return 0
        
        if annual_rate == 0:
            return principal / term_months
        
        # Chuyển lãi suất năm sang tháng
        monthly_rate = annual_rate / 100 / 12
        
        # Công thức tính trả góp đều (annuity)
        payment = principal * (
            monthly_rate * math.pow(1 + monthly_rate, term_months)
        ) / (
            math.pow(1 + monthly_rate, term_months) - 1
        )
        
        return payment
    
    @staticmethod
    def calculate_payment_schedule(
        principal: float,
        annual_rate: float,
        term_months: int
    ) -> List[Dict[str, float]]:
        """
        Tạo bảng kê chi tiết kế hoạch trả nợ
        
        Returns:
            List các kỳ trả nợ với thông tin chi tiết
        """
        schedule = []
        monthly_payment = FinancialCalculator.calculate_monthly_payment(
            principal, annual_rate, term_months
        )
        
        remaining_balance = principal
        monthly_rate = annual_rate / 100 / 12
        
        for month in range(1, term_months + 1):
            # Tính lãi tháng này
            interest_payment = remaining_balance * monthly_rate
            
            # Tính gốc tháng này
            principal_payment = monthly_payment - interest_payment
            
            # Cập nhật số dư
            remaining_balance -= principal_payment
            
            # Đảm bảo tháng cuối số dư = 0
            if month == term_months:
                remaining_balance = 0
            
            schedule.append({
                'month': month,
                'payment': monthly_payment,
                'principal': principal_payment,
                'interest': interest_payment,
                'balance': max(0, remaining_balance)
            })
        
        return schedule
    
    @staticmethod
    def calculate_dsr(
        monthly_payment: float,
        monthly_income: float
    ) -> float:
        """
        Tính Debt Service Ratio (DSR)
        
        Args:
            monthly_payment: Nghĩa vụ trả nợ hàng tháng
            monthly_income: Thu nhập hàng tháng
        
        Returns:
            DSR (%)
        """
        if monthly_income <= 0:
            return 0
        
        return (monthly_payment / monthly_income) * 100
    
    @staticmethod
    def calculate_ltv(
        loan_amount: float,
        collateral_value: float
    ) -> float:
        """
        Tính Loan-to-Value ratio
        
        Args:
            loan_amount: Số tiền vay
            collateral_value: Giá trị tài sản bảo đảm
        
        Returns:
            LTV (%)
        """
        if collateral_value <= 0:
            return 0
        
        return (loan_amount / collateral_value) * 100
    
    @staticmethod
    def calculate_net_cash_flow(
        monthly_income: float,
        living_expenses: float,
        monthly_payment: float
    ) -> float:
        """
        Tính dòng tiền ròng
        
        Args:
            monthly_income: Thu nhập hàng tháng
            living_expenses: Chi phí sinh hoạt
            monthly_payment: Nghĩa vụ trả nợ
        
        Returns:
            Dòng tiền ròng
        """
        return monthly_income - living_expenses - monthly_payment
    
    @staticmethod
    def calculate_safety_margin(
        monthly_income: float,
        living_expenses: float,
        monthly_payment: float
    ) -> float:
        """
        Tính biên an toàn trả nợ
        
        Args:
            monthly_income: Thu nhập hàng tháng
            living_expenses: Chi phí sinh hoạt
            monthly_payment: Nghĩa vụ trả nợ
        
        Returns:
            Biên an toàn (%)
        """
        disposable_income = monthly_income - living_expenses
        
        if disposable_income <= 0:
            return 0
        
        net_after_debt = disposable_income - monthly_payment
        
        return (net_after_debt / disposable_income) * 100
    
    @staticmethod
    def calculate_all_metrics(data: Dict[str, Any]) -> Dict[str, float]:
        """
        Tính toán tất cả các chỉ tiêu tài chính
        
        Args:
            data: Dictionary chứa dữ liệu đầu vào
        
        Returns:
            Dictionary chứa các chỉ tiêu đã tính
        """
        financial_info = data.get('financial_info', {})
        collateral_info = data.get('collateral_info', {})
        
        # Lấy các thông tin cần thiết
        loan_amount = financial_info.get('loan_amount', 0)
        annual_rate = financial_info.get('interest_rate', 0)
        term_months = financial_info.get('loan_term', 0)
        monthly_income = financial_info.get('monthly_income', 0)
        living_expenses = financial_info.get('living_expenses', 0)
        collateral_value = collateral_info.get('market_value', 0)
        
        # Tính các chỉ tiêu
        monthly_payment = FinancialCalculator.calculate_monthly_payment(
            loan_amount, annual_rate, term_months
        )
        
        dsr = FinancialCalculator.calculate_dsr(monthly_payment, monthly_income)
        
        ltv = FinancialCalculator.calculate_ltv(loan_amount, collateral_value)
        
        net_cash_flow = FinancialCalculator.calculate_net_cash_flow(
            monthly_income, living_expenses, monthly_payment
        )
        
        safety_margin = FinancialCalculator.calculate_safety_margin(
            monthly_income, living_expenses, monthly_payment
        )
        
        return {
            'monthly_payment': monthly_payment,
            'monthly_income': monthly_income,
            'living_expenses': living_expenses,
            'dsr': dsr,
            'ltv': ltv,
            'net_cash_flow': net_cash_flow,
            'safety_margin': safety_margin,
            'total_interest': monthly_payment * term_months - loan_amount,
            'total_payment': monthly_payment * term_months
        }
