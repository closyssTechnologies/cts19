from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

import time

import os

username = "info@closyss.com"
password = 12345


def startBot(username, password, url):

    data = {}
    path = 'Users\Sanmeet\Downloads\chromedriver-win64\chromdriver'

    # giving the path of chromedriver to selenium webdriver
    driver = webdriver.Chrome()
    # driver.get("https://www.google.com/")

    action = ActionChains(driver)

    # opening the website  in chrome.
    driver.get(url)

    driver.find_element(By.XPATH, "/html/body/div[1]/header/nav/div/div[1]/ul/li[3]/a").click()
    time.sleep(1)


    # Driver Code
    # Enter below your login credentials

    # find the id or name or class of
    # username by inspecting on username input
    login = driver.find_element(By.NAME,
                                "login")
    login.send_keys(username)
    #
    # # find the password by inspecting on password input
    passw = driver.find_element(By.ID,
                                "password")
    passw.send_keys(password)
    passw.send_keys(Keys.RETURN)
    # passw.submit()

    # driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div/a[7]").click()
    # time.sleep(5)
    #
    # elements = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located(
    #     (By.XPATH, "//html/body/div[1]/div/div[3]/div/table/tbody")))
    #
    # for ele in elements:
    #     print(ele.text)
    #     ele.click()
    #     time.sleep(5)
    #     # driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div[1]/div/div[1]/ol/li[1]/a").click()
    #     # time.sleep(2)
    #
    # time.sleep(10)

    driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div/a[13]").click()
    time.sleep(2)


    driver.find_element(By.XPATH, "//span[text()='Tickets']").click()

    time.sleep(2)

    driver.find_element(By.XPATH, "//a[text()='All Tickets']").click()


    time.sleep(2)
    driver.find_element(By.XPATH, "/html/body/div[1]/div/div[2]/div/table/tbody/tr[20]/td[4]").click()




    time.sleep(2)
    name_field = driver.find_element(By.ID, "name")
    data.update({'name':name_field.get_attribute('value')})


    time.sleep(2)

    driver.get(hitachi_url)

    time.sleep(2)

    hitachi_login = driver.find_element(By.NAME,
                                "user")
    hitachi_login.send_keys('clear.hitachi')
    time.sleep(1)

    passw = driver.find_element(By.NAME,
                                "password")
    passw.send_keys('Hitachi@123')
    passw.send_keys(Keys.RETURN)
    time.sleep(1)

    driver.find_element(By.XPATH, "//*[@id='wrapper']/nav/div/ul[1]/li/a").click()
    time.sleep(2)

    driver.find_element(By.XPATH, "//span[text()=' Incident Tickets ']").click()
    time.sleep(2)

    driver.find_element(By.XPATH, "//a[text()='Manual Incident Ticket Creation']").click()
    time.sleep(5)

    add_remark = driver.find_element(By.NAME, "remarks")
    add_remark.send_keys(data['name'])
    time.sleep(5)










    # driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div[2]/div[1]/div/div/button[1]").click()
    #
    # time.sleep(1)
    #
    # name_field = driver.find_element(By.ID, "name")
    # name_field.send_keys("Test")
    # # print(name_field)
    #
    # time.sleep(1)
    # driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div[1]/div/div[1]/ol/li[2]/div/div/button[1]").click()
    # time.sleep(5)






# URL of the login page of site
# which you want to automate login.
url = "https://csspl.odoo.com/"

hitachi_url = 'https://ftweb.hitachi-payments.com/Vendor/Login'

# Call the function
startBot(username, password, url)




