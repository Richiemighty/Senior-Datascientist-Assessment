import json
import pandas as pd
from datetime import datetime
import re

class CreditBureauFeatureExtractor:
    def __init__(self):
        pass

    def clean_numeric(self, value):
        """Convert string numbers with commas to float"""
        if value is None or isinstance(value, (int, float)):
            return value if value is not None else 0
        if isinstance(value, str) and value.strip() in ('', '-', 'null', 'None'):
            return 0
        try:
            return float(re.sub(r'[^\d.]', '', str(value)))
        except:
            return 0

    def calculate_age(self, birthdate_str):
        """Calculate age from birthdate string"""
        if not birthdate_str or birthdate_str.strip() in ('', '-'):
            return None
        try:
            birthdate = datetime.strptime(birthdate_str, "%d/%m/%Y")
            today = datetime.today()
            return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        except:
            return None

    def process_account_ratings(self, account_rating):
        """Extract good/bad account counts"""
        features = {}
        features['no_of_bad_accounts'] = sum(
            self.clean_numeric(account_rating.get(field, 0))
            for field in [
                'noofotheraccountsbad', 'noofretailaccountsbad', 'nooftelecomaccountsbad',
                'noofautoloanaccountsbad', 'noofhomeloanaccountsbad', 'noofjointloanaccountsbad',
                'noofstudyloanaccountsbad', 'noofcreditcardaccountsbad', 'noofpersonalloanaccountsbad'
            ]
        )
        features['no_of_good_accounts'] = sum(
            self.clean_numeric(account_rating.get(field, 0))
            for field in [
                'noofotheraccountsgood', 'noofretailaccountsgood', 'nooftelecomaccountsgood',
                'noofautoloanccountsgood', 'noofhomeloanaccountsgood', 'noofjointloanaccountsgood',
                'noofstudyloanaccountsgood', 'noofcreditcardaccountsgood', 'noofpersonalloanaccountsgood'
            ]
        )
        return features

    def process_credit_summary(self, credit_summary):
        """Extract debt and arrears information"""
        features = {}
        features['total_outstanding_debt'] = self.clean_numeric(credit_summary.get('totaloutstandingdebt', 0))
        features['total_arrears'] = self.clean_numeric(credit_summary.get('amountarrear', 0))
        features['total_monthly_instalment'] = self.clean_numeric(credit_summary.get('totalmonthlyinstalment', 0))
        features['total_number_of_judgements'] = self.clean_numeric(credit_summary.get('totalnumberofjudgement', 0))
        return features

    def process_enquiry_history(self, enquiry_history):
        """Count recent credit inquiries"""
        features = {'total_recent_enquiries': 0}
        if not enquiry_history:
            return features
            
        recent_count = 0
        for enquiry in enquiry_history:
            try:
                enquiry_date = datetime.strptime(enquiry['daterequested'], "%d/%m/%Y %H:%M:%S")
                if (datetime.now() - enquiry_date).days <= 90:
                    recent_count += 1
            except:
                continue
        features['total_recent_enquiries'] = recent_count
        return features



    def process_credit_agreements(self, credit_agreements):
        """Analyze loan accounts"""
        features = {
            'personal_loan_count': 0,
            'overdraft_count': 0,
            'max_amount_overdue': 0,
            'avg_loan_duration_days': 0,
            'written_off_accounts': 0
        }
        if not credit_agreements:
            return features
            
        total_duration = 0
        valid_durations = 0
        max_overdue = 0
        personal_loans = 0
        overdrafts = 0
        written_off = 0
        
        for account in credit_agreements:
            # Loan type counts
            desc = str(account.get('indicatordescription', '')).lower()
            if 'personal' in desc:
                personal_loans += 1
            if 'overdraft' in desc:
                overdrafts += 1
            
            # Account status
            if account.get('accountstatus') == 'WrittenOff':
                written_off += 1
            
            # Amount overdue
            overdue = self.clean_numeric(account.get('amountoverdue', 0))
            if overdue > max_overdue:
                max_overdue = overdue
            
            # Loan duration
            duration = self.clean_numeric(account.get('loanduration', 0))
            if duration > 0:
                total_duration += duration
                valid_durations += 1
        
        features['personal_loan_count'] = personal_loans
        features['overdraft_count'] = overdrafts
        features['max_amount_overdue'] = max_overdue
        features['written_off_accounts'] = written_off
        if valid_durations > 0:
            features['avg_loan_duration_days'] = total_duration / valid_durations
        
        return features

    def process_delinquency(self, delinquency_info):
        """Extract months in arrears"""
        features = {'max_months_in_arrears': 0}
        if not delinquency_info:
            return features
            
        months = self.clean_numeric(delinquency_info.get('monthsinarrears', 0))
        features['max_months_in_arrears'] = months
        return features

    def process_personal_details(self, personal_details):
        """Extract demographic information"""
        features = {
            'age': self.calculate_age(personal_details.get('birthdate')),
            'property_owned': 1 if personal_details.get('propertyownedtype') else 0,
            'employment_status': 'Employed' if personal_details.get('employerdetail') else 'Unknown'
        }
        return features

    def process_guarantor_info(self, guarantor_details, guarantor_count):
        """Analyze guarantor information"""
        features = {
            'guarantor_count': self.clean_numeric(guarantor_count.get('accounts', 0)),
            'has_guarantor': 0
        }
        
        if guarantor_details:
            for k, v in guarantor_details.items():
                if k != 'guarantordateofbirth' and v not in (None, '', 'null', '1900-01-01T00:00:00+01:00'):
                    features['has_guarantor'] = 1
                    break
        return features

    def extract_features(self, credit_report):
        """Main feature extraction method"""
        features = {'application_id': credit_report.get('application_id')}
        
        if not credit_report or 'data' not in credit_report:
            return features
            
        data = credit_report['data']
        consumer_data = data.get('consumerfullcredit', {})
        
        # Process each data section
        features.update(self.process_account_ratings(consumer_data.get('accountrating', {})))
        features.update(self.process_credit_summary(consumer_data.get('creditaccountsummary', {})))
        features.update(self.process_enquiry_history(consumer_data.get('enquiryhistorytop', [])))
        features.update(self.process_credit_agreements(consumer_data.get('creditagreementsummary', [])))
        features.update(self.process_delinquency(consumer_data.get('deliquencyinformation', {})))
        features.update(self.process_personal_details(consumer_data.get('personaldetailssummary', {})))
        features.update(self.process_guarantor_info(
            consumer_data.get('guarantordetails', {}),
            consumer_data.get('guarantorcount', {})
        ))
        
        return features

    def process_reports(self, credit_reports):
        """Process multiple credit reports into a DataFrame"""
        features_list = []
        
        for report in credit_reports:
            if not isinstance(report, dict) or 'application_id' not in report:
                continue
            features_list.append(self.extract_features(report))
        
        return pd.DataFrame(features_list).set_index('application_id')

